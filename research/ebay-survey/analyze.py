"""German-tank estimates over BFL serials observed in the eBay survey.

Data source: research/ebay-survey/*.webp filenames (operator-verified pass
2026-09-08), cross-checked against label photos. Existing confirmed Jalapeno
serials come from docs/production-census.md.

Grouping is the open question, so every hypothesis is reported rather than
one being picked:
  H1 global      - one BFL sequence for all 6-digit-serial products
  H2 per-model   - each SKU numbered independently
  H3 per-family  - BF00nnG line vs SGLnnnG line vs Monarch
"""

# --- observed serials -------------------------------------------------
# Jalapeno (BF0005G): census + newly photographed in this survey
JALA_CENSUS = [2659, 5794, 7857, 10216, 10265, 13626, 22662, 24991, 24992, 25327]
JALA_NEW    = [6068, 23617, 24017]          # new to the census (photo-verified)
JALA        = sorted(set(JALA_CENSUS + JALA_NEW))

BF0050G  = [2845]                            # 50 GH/s Single, BF00nnG naming
SGL300G  = [2476, 3263, 3522]
SGL600G  = [2397, 5729, 9401]                # label-confirmed
SGL_UNCONF = [2468]                          # 2 connectors, model not on label
MONARCH  = [6422, 6541, 6773, 6890, 7334, 8664]   # 4-digit, separate format


def gt(name, s, note=""):
    s = sorted(set(s)); k = len(s)
    if k < 2:
        print(f"{name:<38} k={k:<2} -- need k>=2 for an estimate {note}")
        return None
    mn, mx = s[0], s[-1]
    gap = (mx - mn) / (k - 1)
    est = mx + gap
    mvue = mx * (k + 1) / k - 1
    print(f"{name:<38} k={k:<2} min={mn:<6} max={mx:<6} gap={gap:>6.0f} "
          f"est={est:>7.0f} MVUE={mvue:>7.0f} +/-{est/k:>6.0f} {note}")
    return est


print("=" * 104)
print("H2 - PER-MODEL (each SKU numbered separately)")
print("=" * 104)
gt("Jalapeno BF0005G", JALA)
gt("Single BF0050G", BF0050G)
gt("Single SGL300G", SGL300G)
gt("Single SGL600G (label-confirmed)", SGL600G)
gt("Single SGL600G (+unconfirmed 2468)", SGL600G + SGL_UNCONF)
gt("Monarch", MONARCH)

print()
print("=" * 104)
print("H3 - PER-FAMILY (naming generation shares a sequence)")
print("=" * 104)
bf = gt("BF00nnG family (Jalapeno + 50G)", JALA + BF0050G)
sgl = gt("SGLnnnG family (300G + 600G)", SGL300G + SGL600G + SGL_UNCONF)
mon = gt("Monarch (own 4-digit sequence)", MONARCH)

print()
print("=" * 104)
print("H1 - GLOBAL (one sequence for all 6-digit products; Monarch excluded)")
print("=" * 104)
glob = gt("ALL BF+SGL pooled", JALA + BF0050G + SGL300G + SGL600G + SGL_UNCONF)

print()
print("=" * 104)
print("INTERLEAVED vs SEPARATE - the Single chassis only")
print("=" * 104)
inter = gt("Singles pooled (interleaved)", BF0050G + SGL300G + SGL600G + SGL_UNCONF)
s3 = gt("  ..split: SGL300G", SGL300G)
s6 = gt("  ..split: SGL600G (+unconf)", SGL600G + SGL_UNCONF)
print(f"{'  ..split: BF0050G':<38} k=1  -- single observation, no estimate")
if inter and s3 and s6:
    print(f"\n  pooled ~{inter:,.0f}   vs   split-sum ~{s3+s6:,.0f} (+BF0050G unknown)"
          f"   difference ~{abs(s3+s6-inter):,.0f}")

print()
print("=" * 104)
print("JALAPENO CENSUS - effect of this survey")
print("=" * 104)
gt("published census (k=10)", JALA_CENSUS)
gt("+ survey serials (k=13)", JALA)
