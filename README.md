[![rank](https://make.fun/badge/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b/rezimtirani/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b-entry/rank.svg)](https://make.fun/bounty/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b)
[![reward](https://make.fun/badge/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b/rezimtirani/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b-entry/reward.svg)](https://make.fun/bounty/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b)
[![make.fun](https://make.fun/badge/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b.svg)](https://make.fun/bounty/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b)

# Fresh-Launch Sniper — Pump.fun Paper Sprint

A paper-trading bot for the [Pump.fun Paper Sprint: Any Bot Can Win](https://make.fun/bounty/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b) bounty on [make.fun](https://make.fun).

## Idea

Most pump.fun coins die within seconds of launch. This bot only buys a fresh
coin once a few strangers have already put real money in, the creator has not
sold, and nobody else has dumped yet. It buys a small fixed stake (0.10 SOL),
then exits on the first of:

- **take-profit** at +25% over cost,
- **stop-loss** at −8% under cost,
- **trailing stop** once the position is +10% up, exiting on an 8% fall from its peak,
- **hold timeout** after 150 slots,
- **creator sold**, or
- **one big sell** (25% or more of the coin's real SOL in a single trade).

At most five positions are open at once, so the bot cycles quickly and can
complete the twenty round trips the guardrails ask for. A 20% equity
drawdown from the peak stops new entries.

## Layout

- `main.py` — the bot. Reads hello / batch / done on stdin per
  `agent-fun/replay/v2`, answers one reply per batch, writes no files.
- `vendor/makefun_bot.py` — the kit's replay shim, vendored as the kit
  instructs (`sdk/python/makefun_bot.py`).

## Run it

With the competition kit:

```bash
node cli/makefun.mjs grade-local --kit . --bot . --driver process
```

## License

MIT. See [LICENSE](LICENSE).
