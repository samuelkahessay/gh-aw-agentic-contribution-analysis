#!/usr/bin/env python3
"""
Branched analysis: per-category signal impact, cross-category reversals,
signal combinations, uncategorized decomposition, enhancement shape,
label-selection effect, and per-category PR linkage.

Outputs:
- data/processed/branched-analysis.json
- findings/branched-summary.md
"""
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median

PROC = Path(__file__).parent.parent / "data" / "processed"
FINDINGS = Path(__file__).parent.parent / "findings"
FINDINGS.mkdir(parents=True, exist_ok=True)

with open(PROC / "community-signals.json") as f:
    signals = json.load(f)

with open(PROC / "issue-pr-linkage.json") as f:
    linkage_data = json.load(f)

community = signals["community_issues"]
closed = [i for i in community if i["state"] == "CLOSED" and i["daysToClose"] is not None]

# ---------------------------------------------------------------------------
# Helpers (matching analyze.py style)
# ---------------------------------------------------------------------------

MIN_N_SIGNAL = 8   # both sides >= 8 for chartable signal
MIN_N_COMBO = 5    # both sides >= 5 for chartable combo


def pct(numerator, denominator):
    return round(numerator * 100 / denominator, 1) if denominator else 0.0


def safe_median(values):
    return round(median(values), 3) if values else None


def safe_mean(values):
    return round(mean(values), 3) if values else None


def analyze_signal(pool, field):
    """Analyze a single boolean signal field within a pool of closed issues."""
    with_signal = [i for i in pool if i[field]]
    without_signal = [i for i in pool if not i[field]]
    with_days = [i["daysToClose"] for i in with_signal]
    without_days = [i["daysToClose"] for i in without_signal]

    delta_pct = None
    if with_days and without_days:
        without_med = median(without_days)
        with_med = median(with_days)
        if without_med > 0:
            delta_pct = round((with_med - without_med) / without_med * 100, 1)

    chartable = len(with_signal) >= MIN_N_SIGNAL and len(without_signal) >= MIN_N_SIGNAL
    return {
        "with": {
            "n": len(with_signal),
            "medianDays": safe_median(with_days),
            "sameDayPct": pct(sum(1 for d in with_days if d < 1), len(with_days)),
        },
        "without": {
            "n": len(without_signal),
            "medianDays": safe_median(without_days),
            "sameDayPct": pct(sum(1 for d in without_days if d < 1), len(without_days)),
        },
        "deltaPct": delta_pct,
        "chartable": chartable,
        "low_n": not chartable,
    }


def analyze_predicate(pool, pred, label="predicate"):
    """Analyze a pool split by an arbitrary predicate function."""
    with_pred = [i for i in pool if pred(i)]
    without_pred = [i for i in pool if not pred(i)]
    with_days = [i["daysToClose"] for i in with_pred]
    without_days = [i["daysToClose"] for i in without_pred]

    delta_pct = None
    if with_days and without_days:
        without_med = median(without_days)
        with_med = median(with_days)
        if without_med > 0:
            delta_pct = round((with_med - without_med) / without_med * 100, 1)

    chartable = len(with_pred) >= MIN_N_COMBO and len(without_pred) >= MIN_N_COMBO
    return {
        "with": {
            "n": len(with_pred),
            "medianDays": safe_median(with_days),
            "sameDayPct": pct(sum(1 for d in with_days if d < 1), len(with_days)),
        },
        "without": {
            "n": len(without_pred),
            "medianDays": safe_median(without_days),
            "sameDayPct": pct(sum(1 for d in without_days if d < 1), len(without_days)),
        },
        "deltaPct": delta_pct,
        "chartable": chartable,
        "low_n": not chartable,
    }


def cluster_summary(pool_all, pool_closed):
    """Compute summary stats for a cluster."""
    days = [i["daysToClose"] for i in pool_closed]
    return {
        "total": len(pool_all),
        "closed": len(pool_closed),
        "closeRate": pct(len(pool_closed), len(pool_all)),
        "medianDays": safe_median(days),
        "sameDayPct": pct(sum(1 for d in days if d < 1), len(days)),
        "copilotDispatchPct": pct(
            sum(1 for i in pool_all if i["copilotDispatched"]), len(pool_all)
        ),
        "avgBodyLength": safe_mean([i["bodyLength"] for i in pool_all]),
        "avgQualityScore": safe_mean([i["qualityScore"] for i in pool_all]),
    }


# ---------------------------------------------------------------------------
# Category pools
# ---------------------------------------------------------------------------

categories = ["bug", "enhancement", "uncategorized", "doc"]
cat_all = {c: [i for i in community if i["category"] == c] for c in categories}
cat_closed = {c: [i for i in closed if i["category"] == c] for c in categories}

# Sanity totals
total_community = len(community)
total_closed = len(closed)

print("=" * 60)
print("META")
print("=" * 60)
print(f"Community issues: {total_community}")
print(f"Closed community issues: {total_closed}")
for c in categories:
    print(f"  {c}: {len(cat_all[c])} total, {len(cat_closed[c])} closed")

meta = {
    "community_total": total_community,
    "closed_total": total_closed,
    "categories": {c: {"total": len(cat_all[c]), "closed": len(cat_closed[c])} for c in categories},
}

# ---------------------------------------------------------------------------
# 1. Per-category signal tables
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("SIGNALS BY CATEGORY")
print("=" * 60)

signal_fields = [
    "hasCodeBlock", "hasErrorOutput", "hasRunLink", "hasFilePath",
    "hasLineNumber", "hasProposedCode", "hasSuggestedFix", "hasReproSteps",
]

signals_by_category = {}
for c in categories:
    pool = cat_closed[c]
    if not pool:
        signals_by_category[c] = {}
        continue
    signals_by_category[c] = {f: analyze_signal(pool, f) for f in signal_fields}
    print(f"\n--- {c} (n={len(pool)} closed) ---")
    for f, result in signals_by_category[c].items():
        flag = "" if result["chartable"] else " [low_n]"
        print(
            f"  {f}: with={result['with']['medianDays']}d (n={result['with']['n']}), "
            f"without={result['without']['medianDays']}d (n={result['without']['n']}), "
            f"delta={result['deltaPct']}%{flag}"
        )

# ---------------------------------------------------------------------------
# 2. Cross-category signal reversals
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("SIGNAL REVERSALS")
print("=" * 60)

signal_reversals = []
main_lanes = ["bug", "enhancement", "uncategorized"]

for f in signal_fields:
    deltas = {}
    for c in main_lanes:
        if c in signals_by_category and f in signals_by_category[c]:
            deltas[c] = signals_by_category[c][f]["deltaPct"]
        else:
            deltas[c] = None

    # Check for sign flip across any pair of lanes
    vals = {c: d for c, d in deltas.items() if d is not None}
    has_reversal = False
    magnitude_ok = False
    if len(vals) >= 2:
        signs = {c: (d > 0) for c, d in vals.items()}
        has_reversal = len(set(signs.values())) > 1
        magnitude_ok = any(abs(d) >= 20 for d in vals.values())

    lead_worthy = has_reversal and magnitude_ok
    entry = {
        "signal": f,
        "deltas": deltas,
        "has_reversal": has_reversal,
        "magnitude_ok": magnitude_ok,
        "lead_worthy": lead_worthy,
    }
    signal_reversals.append(entry)

    flag = " *** LEAD" if lead_worthy else ""
    print(f"  {f}: " + ", ".join(f"{c}={d}%" for c, d in deltas.items()) + flag)

# ---------------------------------------------------------------------------
# 3. Signal combinations
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("SIGNAL COMBINATIONS")
print("=" * 60)

combos = {
    "err+path": lambda i: i["hasErrorOutput"] and i["hasFilePath"],
    "err+fix": lambda i: i["hasErrorOutput"] and i["hasSuggestedFix"],
    "fix+proposed": lambda i: i["hasSuggestedFix"] and i["hasProposedCode"],
    "err+fix+path": lambda i: i["hasErrorOutput"] and i["hasSuggestedFix"] and i["hasFilePath"],
}

signal_combinations = {}
for c in main_lanes:
    pool = cat_closed[c]
    if not pool:
        signal_combinations[c] = {}
        continue
    signal_combinations[c] = {}
    print(f"\n--- {c} (n={len(pool)} closed) ---")
    for combo_name, pred in combos.items():
        result = analyze_predicate(pool, pred, combo_name)
        signal_combinations[c][combo_name] = result
        flag = "" if result["chartable"] else " [low_n]"
        print(
            f"  {combo_name}: with={result['with']['medianDays']}d (n={result['with']['n']}), "
            f"without={result['without']['medianDays']}d (n={result['without']['n']}), "
            f"delta={result['deltaPct']}%{flag}"
        )

# ---------------------------------------------------------------------------
# 4. Uncategorized decomposition
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("UNCATEGORIZED CLUSTERS")
print("=" * 60)

uncat_all = cat_all["uncategorized"]
uncat_closed = cat_closed["uncategorized"]


def is_failure_shaped(i):
    return i["hasErrorOutput"] or i["hasReproSteps"]


def is_change_shaped(i):
    return i["hasSuggestedFix"] and not i["hasErrorOutput"] and not i["hasReproSteps"]


def is_minimal(i):
    return not is_failure_shaped(i) and not is_change_shaped(i)


cluster_defs = {
    "failure_shaped": is_failure_shaped,
    "change_shaped": is_change_shaped,
    "minimal": is_minimal,
}

uncategorized_clusters = {}
for name, pred in cluster_defs.items():
    c_all = [i for i in uncat_all if pred(i)]
    c_closed = [i for i in uncat_closed if pred(i)]
    uncategorized_clusters[name] = cluster_summary(c_all, c_closed)
    s = uncategorized_clusters[name]
    print(
        f"  {name}: n={s['total']} (closed={s['closed']}), "
        f"median={s['medianDays']}d, same-day={s['sameDayPct']}%, "
        f"copilot={s['copilotDispatchPct']}%, "
        f"avgBody={s['avgBodyLength']}, avgQuality={s['avgQualityScore']}"
    )

# ---------------------------------------------------------------------------
# 5. Enhancement shape (bimodality)
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("ENHANCEMENT SHAPE")
print("=" * 60)

enh_closed = cat_closed["enhancement"]
enh_sorted = sorted(enh_closed, key=lambda i: i["daysToClose"])

buckets = {"fast": [], "mid": [], "slow": []}
for i in enh_sorted:
    d = i["daysToClose"]
    if d < 1:
        buckets["fast"].append(i)
    elif d <= 5:
        buckets["mid"].append(i)
    else:
        buckets["slow"].append(i)

enhancement_shape = {}
for bname, bpool in buckets.items():
    days = [i["daysToClose"] for i in bpool]
    enhancement_shape[bname] = {
        "n": len(bpool),
        "medianDays": safe_median(days),
        "minDays": round(min(days), 3) if days else None,
        "maxDays": round(max(days), 3) if days else None,
        "issues": [{"number": i["number"], "title": i["title"], "daysToClose": i["daysToClose"]} for i in bpool],
    }
    print(f"  {bname}: n={len(bpool)}, median={safe_median(days)}d, range=[{enhancement_shape[bname]['minDays']}, {enhancement_shape[bname]['maxDays']}]")

# Bimodality check
fast_n = len(buckets["fast"])
slow_n = len(buckets["slow"])
fast_max = enhancement_shape["fast"]["maxDays"]
slow_min = enhancement_shape["slow"]["minDays"]
gap = round(slow_min - fast_max, 3) if fast_max is not None and slow_min is not None else None

bimodality_usable = (
    fast_n >= 6 and slow_n >= 6
    and gap is not None and gap > 5
)
enhancement_shape["bimodality"] = {
    "fast_n": fast_n,
    "slow_n": slow_n,
    "gap_days": gap,
    "usable": bimodality_usable,
}
print(f"  Bimodality: fast_n={fast_n}, slow_n={slow_n}, gap={gap}d, usable={bimodality_usable}")

# ---------------------------------------------------------------------------
# 6. Label-selection effect (matched comparison)
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("LABEL-SELECTION EFFECT")
print("=" * 60)

# Coarse bins
def body_bin(i):
    bl = i["bodyLength"]
    if bl < 1000:
        return "<1k"
    elif bl < 2500:
        return "1k-2.5k"
    else:
        return "2.5k+"


def quality_bin(i):
    qs = i["qualityScore"]
    if qs <= 1:
        return "0-1"
    elif qs == 2:
        return "2"
    else:
        return "3+"


def matched_comparison(labeled_pool, unlabeled_pool, comparison_name):
    """Compare labeled vs unlabeled across coarse bins. Report shared cells only."""
    labeled_bins = {}
    unlabeled_bins = {}

    for i in labeled_pool:
        key = (body_bin(i), quality_bin(i))
        labeled_bins.setdefault(key, []).append(i)

    for i in unlabeled_pool:
        key = (body_bin(i), quality_bin(i))
        unlabeled_bins.setdefault(key, []).append(i)

    shared_cells = []
    for key in sorted(set(labeled_bins) & set(unlabeled_bins)):
        l_days = [i["daysToClose"] for i in labeled_bins[key]]
        u_days = [i["daysToClose"] for i in unlabeled_bins[key]]
        if not l_days or not u_days:
            continue
        l_med = median(l_days)
        u_med = median(u_days)
        ratio = round(l_med / u_med, 2) if u_med > 0 else None
        shared_cells.append({
            "body_length_bin": key[0],
            "quality_score_bin": key[1],
            "labeled_n": len(l_days),
            "labeled_medianDays": round(l_med, 3),
            "unlabeled_n": len(u_days),
            "unlabeled_medianDays": round(u_med, 3),
            "ratio": ratio,
        })

    # Usable if ratio >= 3x in at least 3 shared cells
    cells_with_3x = sum(1 for c in shared_cells if c["ratio"] is not None and c["ratio"] >= 3)
    usable = cells_with_3x >= 3

    return {
        "comparison": comparison_name,
        "shared_cells": shared_cells,
        "cells_with_3x_ratio": cells_with_3x,
        "usable": usable,
    }


# Labeled bugs vs failure_shaped uncategorized
bugs_closed_pool = cat_closed["bug"]
failure_shaped_closed = [i for i in uncat_closed if is_failure_shaped(i)]

# Labeled enhancements vs change_shaped uncategorized
enh_closed_pool = cat_closed["enhancement"]
change_shaped_closed = [i for i in uncat_closed if is_change_shaped(i)]

label_selection_effect = {
    "bug_vs_failure_shaped": matched_comparison(bugs_closed_pool, failure_shaped_closed, "labeled_bug vs failure_shaped_uncategorized"),
    "enhancement_vs_change_shaped": matched_comparison(enh_closed_pool, change_shaped_closed, "labeled_enhancement vs change_shaped_uncategorized"),
}

for comp_name, comp in label_selection_effect.items():
    print(f"\n--- {comp_name} ---")
    for cell in comp["shared_cells"]:
        print(
            f"  [{cell['body_length_bin']}, {cell['quality_score_bin']}]: "
            f"labeled={cell['labeled_medianDays']}d (n={cell['labeled_n']}), "
            f"unlabeled={cell['unlabeled_medianDays']}d (n={cell['unlabeled_n']}), "
            f"ratio={cell['ratio']}x"
        )
    print(f"  Cells with >=3x ratio: {comp['cells_with_3x_ratio']}, usable: {comp['usable']}")

# ---------------------------------------------------------------------------
# 7. Per-category PR linkage
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("PR LINKAGE BY CATEGORY")
print("=" * 60)

# Build issue-number to category map
issue_category = {i["number"]: i["category"] for i in community}

linkages = linkage_data["linkages"]
merged_linkages = [l for l in linkages if l["prMergedAt"]]

pr_linkage_by_category = {}
for c in main_lanes:
    cat_linkages = [l for l in merged_linkages if issue_category.get(l["issueNumber"]) == c]
    bot_authored = sum(1 for l in cat_linkages if l.get("prAuthorIsBot", False))
    merge_days = [l["issueToMergeDays"] for l in cat_linkages if l.get("issueToMergeDays") is not None]

    pr_linkage_by_category[c] = {
        "merged_prs": len(cat_linkages),
        "bot_authored": bot_authored,
        "bot_authored_pct": pct(bot_authored, len(cat_linkages)),
        "issue_to_merge_median_days": safe_median(merge_days),
    }
    print(
        f"  {c}: merged_prs={len(cat_linkages)}, "
        f"bot={bot_authored} ({pr_linkage_by_category[c]['bot_authored_pct']}%), "
        f"median_merge={pr_linkage_by_category[c]['issue_to_merge_median_days']}d"
    )

# ---------------------------------------------------------------------------
# Lead candidates
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("LEAD CANDIDATES")
print("=" * 60)

lead_candidates = []

# Signal reversals
for rev in signal_reversals:
    if rev["lead_worthy"]:
        lead_candidates.append({
            "type": "signal_reversal",
            "signal": rev["signal"],
            "deltas": rev["deltas"],
            "note": f"{rev['signal']} flips sign across lanes with magnitude >= 20%",
        })
        print(f"  REVERSAL: {rev['signal']} — {rev['deltas']}")

# Enhancement bimodality
if enhancement_shape["bimodality"]["usable"]:
    lead_candidates.append({
        "type": "enhancement_bimodality",
        "gap_days": gap,
        "note": f"Enhancement closure is bimodal: gap of {gap}d between fast and slow clusters",
    })
    print(f"  BIMODALITY: gap={gap}d (usable)")
else:
    print(f"  BIMODALITY: gap={gap}d (NOT usable — fast_n={fast_n}, slow_n={slow_n})")

# Label-selection effect
for comp_name, comp in label_selection_effect.items():
    if comp["usable"]:
        lead_candidates.append({
            "type": "label_selection_effect",
            "comparison": comp_name,
            "cells_with_3x": comp["cells_with_3x_ratio"],
            "note": f"{comp_name}: >=3x ratio in {comp['cells_with_3x_ratio']} matched cells",
        })
        print(f"  LABEL EFFECT: {comp_name} — {comp['cells_with_3x_ratio']} cells with >=3x")
    else:
        print(f"  LABEL EFFECT: {comp_name} — NOT usable ({comp['cells_with_3x_ratio']} cells with >=3x)")

if not lead_candidates:
    print("  (no findings cleared lead thresholds)")

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

results = {
    "meta": meta,
    "signals_by_category": signals_by_category,
    "signal_reversals": signal_reversals,
    "signal_combinations": signal_combinations,
    "uncategorized_clusters": uncategorized_clusters,
    "enhancement_shape": enhancement_shape,
    "label_selection_effect": label_selection_effect,
    "pr_linkage_by_category": pr_linkage_by_category,
    "lead_candidates": lead_candidates,
}

with open(PROC / "branched-analysis.json", "w") as f:
    json.dump(results, f, indent=2)

# ---------------------------------------------------------------------------
# Branched summary
# ---------------------------------------------------------------------------

summary_lines = [
    "# Branched Analysis Summary",
    "",
    "## Sample",
    "",
    f"- Community issues: {meta['community_total']}",
    f"- Closed: {meta['closed_total']}",
]
for c in categories:
    summary_lines.append(f"  - {c}: {meta['categories'][c]['total']} total, {meta['categories'][c]['closed']} closed")

summary_lines += [
    "",
    "## Uncategorized clusters",
    "",
]
for name, s in uncategorized_clusters.items():
    summary_lines.append(
        f"- **{name}**: {s['total']} issues ({s['closed']} closed), "
        f"median {s['medianDays']}d, {s['sameDayPct']}% same-day"
    )

summary_lines += [
    "",
    "## Enhancement shape",
    "",
]
for bname in ["fast", "mid", "slow"]:
    b = enhancement_shape[bname]
    summary_lines.append(f"- **{bname}** (<1d / 1-5d / >5d): n={b['n']}, median={b['medianDays']}d")
summary_lines.append(f"- Bimodality usable: {enhancement_shape['bimodality']['usable']} (gap={gap}d)")

summary_lines += [
    "",
    "## Lead candidates",
    "",
]
if lead_candidates:
    for lc in lead_candidates:
        summary_lines.append(f"- **{lc['type']}**: {lc['note']}")
else:
    summary_lines.append("- No findings cleared lead thresholds.")

summary_lines.append("")

with open(FINDINGS / "branched-summary.md", "w") as f:
    f.write("\n".join(summary_lines))

print(f"\nSaved to {PROC / 'branched-analysis.json'}")
print(f"Saved to {FINDINGS / 'branched-summary.md'}")
