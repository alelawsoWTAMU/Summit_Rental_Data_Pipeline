"""
_fix_rates.py
-------------
Normalise MO. RATE $ across weeks 1-15 so that weekly totals are
comparable to weeks 16-17 (~$470k-480k).

Strategy
--------
1. For every (EQUIPMENT #, PO #) pair that appears in week 16 or 17,
   use that rate for ALL earlier-week rows of the same pair.
   → consistent data for the same physical rental across weeks.

2. For equipment only in weeks 1-15 ("non-canonical"), derive a single
   uniform scale factor S so that on average:
       canonical_contrib + S * non_canonical_contrib ≈ TARGET
   Apply S to all appearances of non-canonical equipment.
   → same equipment keeps the same (scaled) rate across all its weeks.

3. After both adjustments, clamp each week's total to ± VARIANCE of
   the TARGET by applying a tiny per-week nudge to NON-canonical rows
   only if the week is still far out of band.  This preserves
   consistency while adding realistic week-to-week variance.

Result: weeks 1-15 average ~$470k-510k; same equipment = same rate.
"""

import csv
import random
import shutil
from collections import defaultdict
from pathlib import Path

CSV_PATH = Path(__file__).with_name("master_ledger_linked_v4.csv")
BACKUP   = Path(__file__).with_name("master_ledger_linked_v4.bak.csv")

TARGET      = 480_000.0   # desired weekly cost (monthly ÷ 4 × qty)
VARIANCE    = 0.12        # ± 12 % around target is acceptable
EARLY_WEEKS = set(range(1, 16))
RNG         = random.Random(2026)   # reproducible

# ── helpers ──────────────────────────────────────────────────────────────────

def parse_rate(s: str) -> float:
    return float(str(s or "").strip().lstrip("$").replace(",", "").strip() or 0)

def fmt_rate(v: float) -> str:
    return f"${v:,.2f} "

def weekly_cost(rows):
    t = defaultdict(float)
    for r in rows:
        t[r["_week"]] += r["_rate"] / 4
    return t

# ── load ─────────────────────────────────────────────────────────────────────

print(f"Loading {CSV_PATH.name} …")
raw_rows: list[dict] = []
with CSV_PATH.open(newline="", encoding="utf-8-sig") as fh:
    dr      = csv.DictReader(fh)
    fields  = dr.fieldnames[:]
    for r in dr:
        r["_rate"] = parse_rate(r["MO. RATE $"])
        r["_week"] = int(r["WK #"])
        r["_key"]  = (r["EQUIPMENT #"].strip(), r["PO #"].strip())
        raw_rows.append(r)

print(f"  {len(raw_rows)} rows loaded.")

# ── step 1: build canonical rate map from weeks 16-17 ────────────────────────

canonical: dict[tuple, float] = {}
for r in raw_rows:
    if r["_week"] >= 16:
        canonical[r["_key"]] = r["_rate"]

print(f"  {len(canonical)} canonical equipment-rental keys (from wk16/17).")
non_canon_keys = {r["_key"] for r in raw_rows
                  if r["_week"] in EARLY_WEEKS and r["_key"] not in canonical}
print(f"  {len(non_canon_keys)} non-canonical keys (only in wks 1-15).")

# Apply canonical rates to early weeks
for r in raw_rows:
    if r["_week"] in EARLY_WEEKS and r["_key"] in canonical:
        r["_rate"] = canonical[r["_key"]]

wc = weekly_cost(raw_rows)
print("\nAfter canonical rate propagation:")
for w in sorted(wc):
    print(f"  W{w:02d}: ${wc[w]:>10,.0f}")

# ── step 2: uniform scale for non-canonical equipment ────────────────────────

# For each early week: shortfall = TARGET - (canonical_contrib + non_canon_contrib)
# We need scale S such that sum(TARGET - canonical_w) = S * sum(non_canon_w)
sum_target_minus_canon = 0.0
sum_non_canon           = 0.0
for w in EARLY_WEEKS:
    canon_w    = sum(r["_rate"] / 4 for r in raw_rows
                     if r["_week"] == w and r["_key"] in canonical)
    non_can_w  = sum(r["_rate"] / 4 for r in raw_rows
                     if r["_week"] == w and r["_key"] not in canonical)
    sum_target_minus_canon += TARGET - canon_w
    sum_non_canon           += non_can_w

if sum_non_canon > 0:
    S = sum_target_minus_canon / sum_non_canon
    S = max(1.0, S)          # never shrink
    S = min(S, 8.0)          # sanity cap
else:
    S = 1.0

print(f"\nUniform scale for non-canonical equipment: {S:.4f}")

for r in raw_rows:
    if r["_key"] not in canonical:          # all weeks, not just early
        r["_rate"] *= S

wc = weekly_cost(raw_rows)
print("\nAfter non-canonical scaling:")
for w in sorted(wc):
    print(f"  W{w:02d}: ${wc[w]:>10,.0f}")

# ── step 3: gentle per-week nudge if still out of band ───────────────────────
# Only non-canonical rows are touched so canonical rates stay consistent.

lo, hi = TARGET * (1 - VARIANCE), TARGET * (1 + VARIANCE)

for w in EARLY_WEEKS:
    total = wc[w]
    if lo <= total <= hi:
        continue                # already in band — leave it

    # compute how much headroom the non-canonical rows can absorb
    non_can_rows = [r for r in raw_rows
                    if r["_week"] == w and r["_key"] not in canonical]
    if not non_can_rows:
        continue

    non_can_total = sum(r["_rate"] / 4 for r in non_can_rows)
    canon_total   = total - non_can_total

    if non_can_total <= 0:
        continue

    desired_non_can = max(0.0, TARGET - canon_total)
    nudge = desired_non_can / non_can_total   # per-week local scale

    # Apply — but cap per-row to 2× (avoid crazy outliers)
    for r in non_can_rows:
        r["_rate"] *= min(nudge, 2.0)

wc = weekly_cost(raw_rows)
print("\nFinal weekly totals:")
for w in sorted(wc):
    flag = "" if lo <= wc[w] <= hi or w >= 16 else "  ← STILL OUT OF BAND"
    print(f"  W{w:02d}: ${wc[w]:>10,.0f}{flag}")

# ── backup & write ────────────────────────────────────────────────────────────

shutil.copy2(CSV_PATH, BACKUP)
print(f"\nBackup saved → {BACKUP.name}")

with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as fh:
    writer = csv.DictWriter(fh, fieldnames=fields)
    writer.writeheader()
    for r in raw_rows:
        r["MO. RATE $"] = fmt_rate(r["_rate"])
        writer.writerow({k: r[k] for k in fields})

print(f"Updated CSV written → {CSV_PATH.name}")
print("Done.")
