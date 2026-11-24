[![rank](https://make.fun/badge/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b/rezimtirani/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b-entry/rank.svg)](https://make.fun/bounty/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b)
[![reward](https://make.fun/badge/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b/rezimtirani/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b-entry/reward.svg)](https://make.fun/bounty/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b)
[![make.fun](https://make.fun/badge/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b.svg)](https://make.fun/bounty/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b)

# Burst Scalp — Pump.fun Paper Sprint

A paper-trading bot for the [Pump.fun Paper Sprint: Any Bot Can Win](https://make.fun/bounty/u-boothlord-pump-fun-paper-sprint-any-bot-can-f83c389b) bounty on [make.fun](https://make.fun).

## Idea

A coin's launch burst is instant and its price then decays, slowly and
relentlessly, back toward its launch price. Buying after the burst means
buying the top and riding the bleed. So this bot buys in a coin's first
two slots, while its price is still within 20% of launch, takes a small
take-profit (+3%) or a small stop-loss (−2%), and is out within twenty
slots. Stakes are capped by the harness at 1% of the coin's real SOL, so
early stakes are small — which also keeps each loss small. The creator
must not have sold and no one may have dumped yet.

On the kit's 24-hour dev window this scores −0.111 SOL (−1.11%) over 152
round trips: it loses a little, honestly. It is the least-bad of five
strategies tried; the burst is where the money is, and the harness's
two-slot order latency plus fees eat most of it.

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
