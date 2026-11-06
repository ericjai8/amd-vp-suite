"""
Python mirror of the Pine v4+ continuous AMD logic, for checking boxes on past data.
Fixes under test:
  * typical candle = median candle over the last 24 HOURS (not 2h), so a sweep's big
    candles can't loosen the limits
  * remember the LAST valid range (for up to `stale_bars` bars); when price breaks it,
    lock that range as A, even if the range ending on the previous bar isn't valid
  * lead-in trim: opening bars outside the core (last 2/3) are dropped
  * V / U check: the middle third must sit in the middle of the box
Usage: python continuous_sim.py  (needs ../../fast-pass-lab/lab for the data loader)
"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "fast-pass-lab", "lab"))
import data as D

P = dict(max_look=96, min_bars=12, k_h=8.0, max_er=0.30, max_r2=0.40, imp_bars=6, imp_k=4.0, imp_er=0.5,
         touches=2, zone=0.20, med_bars=288, stale_bars=12, sweep_ticks=2, depth_pct=75, reclaim_bars=6,
         retest_ticks=8, retest_bars=36, fail_closes=2, trim_tol=0.15, mid_lo=0.25)
TICK = 0.25


def detect_ranges(o, h, l, c, P):
    n = len(c)
    rng = pd.Series(h - l)
    med = rng.rolling(P["med_bars"], min_periods=50).median().to_numpy()
    imp_net = np.abs(c - np.r_[np.full(P["imp_bars"], np.nan), c[:-P["imp_bars"]]])
    dc = np.abs(np.diff(c, prepend=c[0]))
    imp_path = pd.Series(dc).rolling(P["imp_bars"]).sum().to_numpy()
    rlen = np.zeros(n, int); rhi = np.full(n, np.nan); rlo = np.full(n, np.nan)
    for t in range(P["max_look"] + P["imp_bars"] + 2, n):
        m = med[t]
        if not m > 0:
            continue
        hh, ll, path = h[t], l[t], 0.0
        S = np.zeros(9); S[0] = 1.0     # S0..S4, Sy, Sxy, Sx2y, Syy
        for j in range(1, P["max_look"] + 1):
            b = t - j
            if imp_path[b] > 0 and imp_net[b] >= P["imp_k"] * m and imp_net[b] / imp_path[b] >= P["imp_er"]:
                break
            nh, nl = max(hh, h[b]), min(ll, l[b])
            if (nh - nl) / m > P["k_h"]:
                break
            hh, ll = nh, nl
            path += abs(c[b + 1] - c[b])
            x = float(j); y = c[b] - c[t]
            S += [1, x, x * x, x ** 3, x ** 4, y, x * y, x * x * y, y * y]
            ln = j + 1
            if ln >= P["min_bars"]:
                er = abs(c[t] - c[b]) / path if path > 0 else 1
                if er <= P["max_er"]:
                    S0, S1, S2, S3, S4, Sy, Sxy, Sx2y, Syy = S
                    A = np.array([[S4, S3, S2], [S3, S2, S1], [S2, S1, S0]])
                    if abs(np.linalg.det(A)) > 1e-9:
                        qa, qb, qc = np.linalg.solve(A, [Sx2y, Sxy, Sy])
                        sst = Syy - Sy * Sy / S0
                        ssr = Syy - (qa * Sx2y + qb * Sxy + qc * Sy)
                        r2 = 1 - ssr / sst if sst > 0 else 0
                        if r2 <= P["max_r2"]:
                            rlen[t] = ln
        ln = rlen[t]
        if ln:
            # lead-in trim (same as Pine): drop opening bars that poke outside the core
            # (last 2/3 of the range) - that's the tail of the prior move
            cs = t - (2 * ln) // 3
            cH, cL = h[cs:t + 1].max(), l[cs:t + 1].min()
            tol = P["trim_tol"] * (cH - cL)
            s0 = t - ln + 1
            while s0 < cs and (h[s0] > cH + tol or l[s0] < cL - tol):
                s0 += 1
            if t - s0 + 1 >= P["min_bars"]:
                rlen[t], rhi[t], rlo[t] = t - s0 + 1, h[s0:t + 1].max(), l[s0:t + 1].min()
            else:
                rlen[t] = 0
    return rlen, rhi, rlo


def edge_tests(h, l, a, b, hi, lo, zone):
    z = (hi - lo) * zone; tH = tL = 0; inH = inL = False
    for k in range(a, b + 1):
        x, y = h[k] >= hi - z, l[k] <= lo + z
        tH += x and not inH; tL += y and not inL; inH, inL = x, y
    return tH, tL


def run(df, P=P):
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    rlen, rhi, rlo = detect_ranges(o, h, l, c, P)
    n = len(c); events = []; boxes = []
    st = 0; last = None          # last valid range: (start, end, hi, lo)
    for t in range(1, n):
        if st == 0:
            if rlen[t - 1] >= P["min_bars"]:
                last = (t - rlen[t - 1], t - 1, rhi[t - 1], rlo[t - 1])
            if last and t - 1 - last[1] <= P["stale_bars"]:
                s, e, hi, lo = last
                dn = l[t] <= lo - P["sweep_ticks"] * TICK
                up = h[t] >= hi + P["sweep_ticks"] * TICK
                if dn or up:
                    tH, tL = edge_tests(h, l, s, e, hi, lo, P["zone"])
                    m0, m1 = s + (e - s + 1) // 3, s + 2 * (e - s + 1) // 3
                    mid_pos = (c[m0:m1 + 1].mean() - lo) / (hi - lo)     # V / U check
                    if tH >= P["touches"] and tL >= P["touches"] and P["mid_lo"] <= mid_pos <= 1 - P["mid_lo"]:
                        boxes.append((s, e, hi, lo)); st = 2; d = 1 if dn else -1
                        ext = l[t] if dn else h[t]; sb = t; aHi, aLo = hi, lo
                        # POC: volume profile of the box (40 rows)
                        rows = 40; step = (hi - lo) / rows; vol = np.zeros(rows)
                        for k in range(s, e + 1):
                            r0 = int(np.clip((l[k] - lo) // step, 0, rows - 1)); r1 = int(np.clip((h[k] - lo) // step, 0, rows - 1))
                            vol[r0:r1 + 1] += df.volume.iloc[k] / (r1 - r0 + 1)
                        poc = lo + (vol.argmax() + 0.5) * step
                        last = None
            continue
        if st == 2:
            ext = min(ext, l[t]) if d == 1 else max(ext, h[t])
            depth = aLo - ext if d == 1 else ext - aHi
            if depth > P["depth_pct"] / 100 * (aHi - aLo):
                events.append((t, "breakout")); st = 0
            elif (d == 1 and c[t] > aLo) or (d == -1 and c[t] < aHi):
                events.append((t, "M")); st = 3
            elif t - sb >= P["reclaim_bars"]:
                events.append((t, "no reclaim")); st = 0
        elif st == 3:
            if (d == 1 and c[t] > poc) or (d == -1 and c[t] < poc):
                events.append((t, "D")); st = 4; pb = t; fails = 0
            elif (d == 1 and c[t] < ext) or (d == -1 and c[t] > ext):
                events.append((t, "invalid")); st = 0
        elif st == 4 and t > pb:
            touched = l[t] <= poc + P["retest_ticks"] * TICK if d == 1 else h[t] >= poc - P["retest_ticks"] * TICK
            right = c[t] > poc if d == 1 else c[t] < poc
            if not right:
                fails += 1
                if fails >= P["fail_closes"]:
                    events.append((t, "x POC")); st = 0
            elif touched:
                events.append((t, "ok POC")); st = 0
            elif t - pb > P["retest_bars"]:
                events.append((t, "no retest")); st = 0
    return boxes, events


if __name__ == "__main__":
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    df = D.load("5m")
    df = df[df.index >= pd.Timestamp("2026-09-01", tz="UTC")]
    boxes, events = run(df)
    print("boxes:", len(boxes), "events:", pd.Series([e for _, e in events]).value_counts().to_dict())
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    idx = df.index.tz_convert("America/New_York")
    pick = [b for b in boxes][::max(1, len(boxes) // 16)][:16]
    fig, axs = plt.subplots(4, 4, figsize=(24, 20))
    for ax, (s, e, hi, lo) in zip(axs.flat, pick):
        a0, a1 = max(0, s - 60), min(len(c), e + 80)
        for x in range(a0, a1):
            col = "#26a69a" if c[x] >= o[x] else "#ef5350"
            ax.plot([x, x], [l[x], h[x]], color=col, lw=0.7); ax.plot([x, x], [o[x], c[x]], color=col, lw=2.5)
        ax.add_patch(plt.Rectangle((s, lo), e - s, hi - lo, alpha=0.18, color="gold"))
        for t, ev in events:
            if a0 <= t < a1 and t > e:
                ax.annotate(ev, (t, h[t] if ev in ("M", "D") else l[t]), color="w", fontsize=8,
                            bbox=dict(boxstyle="round", fc={"M": "purple", "D": "teal", "ok POC": "green", "x POC": "red"}.get(ev, "gray")))
        ax.set_title(f"{idx[s]:%a %m-%d %H:%M} ET  A {e - s + 1} bars, {hi - lo:.0f} pts", color="w")
        ax.set_facecolor("#111"); ax.set_xticks([]); ax.tick_params(colors="w")
    fig.patch.set_facecolor("#111"); plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(os.path.abspath(__file__)), "continuous_samples.png"), dpi=75)
