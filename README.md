# AMD + VP Suite

A TradingView Pine v6 strategy that combines a built-in volume profile with ICT's AMD sequence (Accumulation, Manipulation, Distribution) and a POC-retest entry. It also marks liquidity, sets stops and targets, and sends Discord-ready alerts.

**File:** `tradingview/amd_vp_suite.pine`

## How the setup works

| Step | What the script looks for |
|---|---|
| **A: Accumulation** | Inside a search window (default: Asia, 6pm to 2am ET), it finds the latest tight range. It grows the range backward from the window's last bar while the range stays under 0.4× the daily ATR from prior days. The range has to be at least 12 bars long, its net move has to be under 50% of the range, and each edge has to be tested at least twice. If any rule fails, the script draws "no accumulation" and doesn't look for AMD that day. It profiles the range it found, works out POC, VAH, and VAL, and draws the profile with buy volume and sell volume in separate colors. |
| **M: Manipulation** | After that session ends, price sweeps beyond the range by at least 2 ticks and no deeper than 75% of the range height. It then closes back inside the range within 6 bars. |
| **D: Distribution** | Price closes beyond the POC in the direction of the reclaim. |
| **✓ POC: retest confirmed** | Price pulls back to within 8 ticks of the POC and closes back on the right side. The script enters on that close. |
| **✗ POC: retest failed** | Two closes land on the wrong side of the POC. |
| **Invalid** | Price closes beyond the sweep's extreme, so the move wasn't a sweep after all. |

### Stops, targets, and exits

- **Stop:** choose one of three placements: the retest candle, the higher low or range edge (default), or the sweep extreme (the LL). Whichever you pick, the stop is never closer than 0.5 ATR.
- **Size:** contracts = dollar risk ÷ (stop points × point value), capped. A wide stop means fewer contracts.
- **T1:** the next liquidity level that hasn't been taken yet. Candidates are untaken swing highs and lows, the range high or low, and PDH or PDL. If T1 is less than 1.5R away, the trade is skipped.
- **T2:** the next liquidity level after T1.
- **Exits:** 50% of the position comes off at T1. The rest go to T2, with the stop moved to breakeven once T1 fills. Everything is closed at 4:55pm ET.

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

## Status

The script hasn't been backtested outside TradingView. Use the Strategy Tester and paper trading to see how it performs, and log each trade.
