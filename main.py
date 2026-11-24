#!/usr/bin/env python3
"""Burst Scalp — a paper-trading bot for the pump.fun replay.

What the dev window actually shows: a coin's launch burst is instant and
its price then decays, slowly and relentlessly, back toward its launch
price. Buying after the burst means buying the top and riding the bleed;
every slower strategy I tested on this window loses money. The one entry
that comes out near breakeven is the earliest one: buy in the first two
slots, while the price is still within 20% of launch, take a small
take-profit (+3%) or a small stop-loss (-2%), and be out within twenty
slots. Stakes are capped by the harness at 1% of the coin's real SOL, so
early stakes are small — which also keeps each loss small.

The creator must not have sold and no one may have dumped yet. Positions
are capped at five, but a twenty-slot hold means the cap rarely binds.

The bot speaks agent-fun/replay/v2 through the vendored shim: it reads
hello / batch / done on stdin and answers one reply per batch. It never
writes a file, never reads the clock or the environment, and never uses
unseeded randomness, so two runs on the same data produce the same
action log. All per-coin history is kept in insertion-ordered dicts.

Run locally with the kit:
  node cli/makefun.mjs grade-local --kit . --bot <repo> --driver process
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bot  # noqa: E402  (after the sys.path line: -P leaves the script directory off sys.path)

SOL = makefun_bot.LAMPORTS_PER_SOL

# --- sizing -----------------------------------------------------------------
STAKE_LAMPORTS = SOL // 10          # 0.10 SOL per coin (cap-limited in practice)
MIN_BUY_LAMPORTS = SOL // 100        # 0.01 SOL: the guardrail's minimum buy; the
                                     # size cap only allows this much this early,
                                     # and a 0.02 floor would skip most bursts
MIN_ROUND_TRIP_LAMPORTS = SOL // 100  # 0.01 SOL: guardrail's minimum buy

# --- entries ----------------------------------------------------------------
EVAL_MIN_AGE = 0        # a coin may be bought in its creation batch
EVAL_MAX_AGE = 2        # ... and no later than two slots after creation
MIN_REAL_SOL = SOL                  # coin must hold at least 1 SOL (cap >= 0.01 SOL)
MAX_REAL_SOL = SOL * 30             # ... and at most 30 SOL at decision time
MIN_PRICE_VS_CREATE = 100  # price must be at or above its launch price
MAX_PRICE_VS_CREATE = 120  # ... and at most 20% above it: still early in the burst
MAX_SELL_SHARE = 10     # sells by others at most 10% of their buys

# --- exits ------------------------------------------------------------------
TAKE_PROFIT_PCT = 103   # sell everything at +3% over cost
STOP_LOSS_PCT = 98      # sell everything at -2% under cost
TRAIL_ARM_PCT = 1000    # trailing stop disabled: a 3% target leaves no room for it
TRAIL_DROP_PCT = 5      # (kept for the exit check's shape)
HOLD_SLOTS = 20         # sell everything after 20 slots held
BIG_SELL_SHARE = 4      # one sell of 25% or more of real SOL ends the trade

BUY_SLIPPAGE_BPS = 500
SELL_SLIPPAGE_BPS = 10000  # a crashing coin must be sold at any price
DRAWDOWN_STOP_PCT = 20  # stop new entries once equity is 20% below its peak


class Tape:
    """What the bot has seen on one coin, in the order it happened."""

    __slots__ = (
        "mint", "creator", "born", "v0", "t0",
        "dev_buy", "dev_sold", "buyers",
        "buy_sol", "sell_sol", "biggest_sell", "trades", "decided",
    )

    def __init__(self, mint, creator, born):
        self.mint = mint
        self.creator = creator
        self.born = born
        self.v0 = 0
        self.t0 = 0
        self.dev_buy = 0
        self.dev_sold = False
        self.buyers = {}
        self.buy_sol = 0
        self.sell_sol = 0
        self.biggest_sell = 0
        self.trades = 0
        self.decided = False

    def note_trade(self, event):
        """Fold one TradeEvent into the tape."""
        sol = int(event["sol_amount"])
        self.trades += 1
        if event["user"] == self.creator:
            if event["is_buy"]:
                self.dev_buy += sol
            else:
                self.dev_sold = True
            return
        if event["is_buy"]:
            self.buy_sol += sol
            self.buyers[event["user"]] = self.buyers.get(event["user"], 0) + 1
        else:
            self.sell_sol += sol
            if sol > self.biggest_sell:
                self.biggest_sell = sol


class Book:
    """The bot's own memory: tapes, open positions and the equity peak."""

    def __init__(self):
        self.tapes = {}
        self.held = {}
        self.peak_equity = 0
        self.stopped = False

    def tape_for(self, event):
        tape = self.tapes.get(event["mint"])
        if tape is None:
            tape = Tape(event["mint"], event.get("creator", ""), event["slot"])
            self.tapes[event["mint"]] = tape
        return tape


BOOK = Book()


def coin_value_lamports(state, mint, holding):
    """Marked value of a holding from the curve's latest reserves."""
    curve = state.curves.get(mint)
    if curve is None or curve.virtual_token_reserves <= 0:
        return holding.cost_lamports
    return holding.token_amount * curve.virtual_quote_reserves // curve.virtual_token_reserves


def equity_lamports(state):
    """Cash plus the marked value of every open position."""
    total = state.cash
    for mint, holding in state.positions.items():
        total += coin_value_lamports(state, mint, holding)
    return total


def refresh_positions(state):
    """Sync the held book with the account: add new positions, drop closed ones."""
    now = state.slot
    for mint in list(BOOK.held):
        if mint not in state.positions:
            del BOOK.held[mint]
    for mint, holding in state.positions.items():
        curve = state.curves.get(mint)
        if curve is not None and curve.complete:
            continue
        value = coin_value_lamports(state, mint, holding)
        ratio = value * 100 // holding.cost_lamports if holding.cost_lamports > 0 else 100
        slot_held = BOOK.held.get(mint)
        if slot_held is None:
            BOOK.held[mint] = {"slot": now, "peak": ratio}
        elif ratio > slot_held["peak"]:
            slot_held["peak"] = ratio


def exit_orders(state):
    """Sell orders for every position that hit an exit rule."""
    orders = []
    for mint, holding in state.positions.items():
        curve = state.curves.get(mint)
        if curve is None or curve.complete:
            continue
        info = BOOK.held.get(mint)
        if info is None:
            continue
        value = coin_value_lamports(state, mint, holding)
        ratio = value * 100 // holding.cost_lamports if holding.cost_lamports > 0 else 100
        tape = BOOK.tapes.get(mint)
        reason = None
        if ratio >= TAKE_PROFIT_PCT:
            reason = "take-profit"
        elif ratio <= STOP_LOSS_PCT:
            reason = "stop-loss"
        elif info["peak"] >= TRAIL_ARM_PCT and ratio <= info["peak"] * (100 - TRAIL_DROP_PCT) // 100:
            reason = "trailing-stop"
        elif state.slot - info["slot"] >= HOLD_SLOTS:
            reason = "hold-timeout"
        elif tape is not None and tape.dev_sold:
            reason = "creator-sold"
        elif tape is not None and curve.real_quote_reserves > 0 and tape.biggest_sell * BIG_SELL_SHARE >= curve.real_quote_reserves:
            reason = "big-sell"
        if reason is not None:
            orders.append({
                "side": "sell",
                "mint": mint,
                "token_amount": holding.token_amount,
                "max_slippage_bps": SELL_SLIPPAGE_BPS,
            })
    return orders


def entry_orders(state):
    """Buy orders for coins still within 20% of their launch price, aged 0-2 slots."""
    if BOOK.stopped:
        return []
    caps = state.hello["caps"]
    tx = state.tx_fee_lamports()
    free = state.free_cash_lamports()
    slots = caps["max_open_positions"] - state.committed_position_count()
    orders = []
    for mint, tape in BOOK.tapes.items():
        if len(orders) >= caps["max_orders_per_batch"] or slots <= 0:
            break
        if tape.decided:
            continue
        age = state.slot - tape.born
        if age < EVAL_MIN_AGE:
            continue
        if age > EVAL_MAX_AGE:
            tape.decided = True
            continue
        curve = state.curves.get(mint)
        if curve is None or curve.complete:
            tape.decided = True
            continue
        # Still within the launch band: at or above launch, at most 20% above it.
        if tape.v0 > 0:
            if curve.virtual_quote_reserves * tape.t0 * 100 < tape.v0 * curve.virtual_token_reserves * MIN_PRICE_VS_CREATE:
                continue
            if curve.virtual_quote_reserves * tape.t0 * 100 > tape.v0 * curve.virtual_token_reserves * MAX_PRICE_VS_CREATE:
                continue
        if tape.dev_sold:
            continue
        if tape.buy_sol > 0 and tape.sell_sol * 100 > tape.buy_sol * MAX_SELL_SHARE:
            continue
        if curve.real_quote_reserves < MIN_REAL_SOL or curve.real_quote_reserves > MAX_REAL_SOL:
            continue
        cap = state.max_buy_lamports(mint)
        if cap < MIN_BUY_LAMPORTS:
            continue
        tape.decided = True
        amount = min(cap, STAKE_LAMPORTS)
        if free < amount + tx:
            continue
        orders.append({
            "side": "buy",
            "mint": mint,
            "quote_lamports": amount,
            "max_slippage_bps": BUY_SLIPPAGE_BPS,
        })
        free -= amount + tx
        slots -= 1
    return orders


def on_batch(state, batch):
    """One reply per batch: fold the events in, exit losers, scalp the burst."""
    for event in batch["events"]:
        kind = event["event"]
        if kind == "CreateEvent":
            tape = BOOK.tape_for(event)
            tape.creator = event.get("creator", tape.creator)
            tape.born = event["slot"]
            tape.v0 = int(event["virtual_quote_reserves"])
            tape.t0 = int(event["virtual_token_reserves"])
        elif kind == "TradeEvent":
            BOOK.tape_for(event).note_trade(event)
        else:
            tape = BOOK.tapes.get(event["mint"])
            if tape is not None:
                tape.decided = True
    refresh_positions(state)
    equity = equity_lamports(state)
    if equity > BOOK.peak_equity:
        BOOK.peak_equity = equity
    elif BOOK.peak_equity > 0 and equity * 100 <= BOOK.peak_equity * (100 - DRAWDOWN_STOP_PCT):
        BOOK.stopped = True
    orders = exit_orders(state)
    orders.extend(entry_orders(state))
    return orders


if __name__ == "__main__":
    makefun_bot.run(on_batch)
