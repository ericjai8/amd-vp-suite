# AMD + VP Suite

A TradingView Pine v6 strategy that combines a built-in volume profile with ICT's AMD sequence (Accumulation, Manipulation, Distribution) and a POC-retest entry. It also marks liquidity, sets stops and targets, and sends Discord-ready alerts.

**File:** `tradingview/amd_vp_suite.pine`

## How the setup works

Rules are set in minutes, not bars, so they behave the same on 1m, 5m, or 30m. The defaults are tuned for 5m.

| Step | What the script looks for |
|---|---|
| **A: Accumulation** | Checked on every bar, in any session. Working back from the current bar, the recent bars count as accumulation when all of these hold: the range starts where the last impulse leg ended, it's no taller than 8 median candles (median measured over the last 24 hours, so sweep candles can't loosen it), it's choppy (efficiency ≤ 0.30), it has no trend or arc shape (quadratic-fit R² ≤ 0.40), it lasts at least 60 minutes, and both edges have been tested at least twice. Opening bars that stick out of the range's core (its last two-thirds) are trimmed off, since they're the tail of the move before the chop. When price breaks the most recent valid range (if it was valid within the last 60 minutes), that range is locked in as **A**, as long as it isn't a V or U shape (the middle third has to sit mid-box). Its volume profile (POC, VAH, VAL) is drawn with buy and sell volume in separate colors. A dotted box shows the range while it forms. |
| **M: Manipulation** | Price sweeps beyond the range by at least 2 ticks and no deeper than 75% of the range height. It then closes back inside the range within 30 minutes. If it goes deeper, or doesn't come back in time, it's treated as a real breakout and the script resumes scanning. |
| **D: Distribution** | Price closes beyond the POC in the direction of the reclaim. |
| **✓ POC: retest confirmed** | Price pulls back to within 8 ticks of the POC and closes back on the right side. The script enters on that close. |
| **✗ POC: retest failed** | Two closes land on the wrong side of the POC. |
| **Invalid** | Price closes beyond the sweep's extreme, so the move wasn't a sweep after all. |

### Stops, targets, and exits

- **Stop:** choose one of three placements: the retest candle, the higher low or range edge (default), or the sweep extreme (the LL). Whichever you pick, the stop is never closer than 0.5 ATR.
- **Size:** contracts = dollar risk ÷ (stop points × point value), capped. A wide stop means fewer contracts.
- **T1:** the next liquidity level that hasn't been taken yet. Candidates are untaken swing highs and lows, the range high or low, and PDH or PDL. If T1 is less than 1.5R away, the trade is skipped.
- **T2:** the next liquidity level after T1.
- **Exits:** 50% of the position comes off at T1. The rest go to T2, with the stop moved to breakeven once T1 fills. Everything is closed at 4:55pm ET, and no new entries are taken after 4:25pm (prop rule; this can be turned off).

## Alerts

Pick **Order fills and alert() function calls** as the alert type and point the webhook at your Discord channel. The script writes its own JSON for the setup alerts. Order fills (T1, T2, Stop, BE, Flat) use the alert's Message box, so paste this into it:

```
{"content": "AMD VP | {{strategy.order.comment}} | {{strategy.order.action}} {{strategy.order.contracts}} {{ticker}} @ {{strategy.order.price}}"}
```

It sends an alert for each of these events:

- Manipulation
- POC reclaim
- Confirmed entry, with the stop, T1, and T2
- Failed retest
- Invalid setup

## Checking the boxes

`research/continuous_sim.py` runs the same detection logic in Python on 5m MNQ data and saves `research/continuous_samples.png` (16 sample A boxes). On Sep–Oct 2026, about 12 of 16 samples were clean sideways chop with the lead-in move excluded; the misses were wide U shapes or ranges that drifted at one end.

## Status

The script hasn't been backtested outside TradingView. Use the Strategy Tester and paper trading to see how it performs, and log each trade.
