#!/usr/bin/env python3
"""
Full analysis for "The Agent Interface" blog post.

Produces findings for all 7 sub-sections:
4.1 Platform composition (bot vs human)
4.2 Two intake paths (community vs maintainer)
4.3 Controllable signals ranked by impact
4.4 The decision-free threshold
4.5 What reporters can't control
4.6 Contributor archetypes
4.7 The missing metric (issue-side quality)

Outputs: data/processed/analysis-results.json
         findings/*.md (per-finding writeups)
"""
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median, mean, stdev

PROC = Path(__file__).parent.parent / "data" / "processed"
FINDINGS = Path(__file__).parent.parent / "findings"
FINDINGS.mkdir(parents=True, exist_ok=True)

with open(PROC / "community-signals.json") as f:
    signals = json.load(f)

with open(PROC / "author-classification.json") as f:
    author_data = json.load(f)

with open(PROC / "issue-pr-linkage.json") as f:
    linkage_data = json.load(f)

community = signals["community_issues"]
maintainer = signals["maintainer_issues"]
timeline = signals["timeline"]

# Helper
def safe_median(vals):
    return median(vals) if vals else None

def safe_mean(vals):
    return mean(vals) if vals else None

def pct(n, total):
    return round(n * 100 / total, 1) if total else 0


# ============================================================
# 4.1: Platform composition
# ============================================================
print("=" * 60)
print("4.1: PLATFORM COMPOSITION")
print("=" * 60)

total = signals["summary"]["total"]
bot_count = signals["summary"]["bot_count"]
community_count = signals["summary"]["community_count"]
maintainer_count = signals["summary"]["maintainer_count"]

print(f"Total issues: {total}")
print(f"Bot: {bot_count} ({pct(bot_count, total)}%)")
print(f"Maintainer: {maintainer_count} ({pct(maintainer_count, total)}%)")
print(f"Community: {community_count} ({pct(community_count, total)}%)")
print(f"Ratio: 1 community issue for every {bot_count // community_count} bot issues")

composition = {
    "total": total,
    "bot": {"count": bot_count, "pct": pct(bot_count, total)},
    "maintainer": {"count": maintainer_count, "pct": pct(maintainer_count, total)},
    "community": {"count": community_count, "pct": pct(community_count, total)},
    "ratio_bot_per_community": bot_count // community_count,
    "timeline": timeline,
}

# ============================================================
# 4.2: Two intake paths
# ============================================================
print(f"\n{'=' * 60}")
print("4.2: TWO INTAKE PATHS")
print("=" * 60)

# Community label coverage
community_labeled = author_data["summary"]["community_labeled"]
human_filed = author_data["summary"]["human_filed"]
human_without = author_data["summary"]["human_without_community"]

print(f"Human-filed issues: {human_filed}")
print(f"With community label: {community_labeled} ({pct(community_labeled, human_filed)}%)")
print(f"Without (maintainers): {human_without} ({pct(human_without, human_filed)}%)")

# Label distribution on community issues
label_counts = Counter()
for issue in community:
    for label in issue["labels"]:
        label_counts[label] += 1

print(f"\nTop labels on community issues:")
for label, count in label_counts.most_common(15):
    print(f"  {label}: {count} ({pct(count, len(community))}%)")

intake_paths = {
    "human_filed": human_filed,
    "community_labeled": community_labeled,
    "maintainer_unlabeled": human_without,
    "community_label_rate": pct(community_labeled, human_filed),
    "top_labels": dict(label_counts.most_common(15)),
}

# ============================================================
# 4.3: Controllable signals ranked by impact
# ============================================================
print(f"\n{'=' * 60}")
print("4.3: CONTROLLABLE SIGNALS")
print("=" * 60)

closed = [i for i in community if i["state"] == "CLOSED" and i["daysToClose"] is not None]

def analyze_signal(name, condition, subset=None):
    pool = subset or closed
    with_signal = [i for i in pool if condition(i)]
    without_signal = [i for i in pool if not condition(i)]

    with_days = [i["daysToClose"] for i in with_signal]
    without_days = [i["daysToClose"] for i in without_signal]

    w_med = safe_median(with_days)
    wo_med = safe_median(without_days)
    delta_pct = None
    if w_med is not None and wo_med is not None and wo_med > 0:
        delta_pct = round((w_med - wo_med) / wo_med * 100, 1)

    w_same_day = sum(1 for d in with_days if d < 1)
    wo_same_day = sum(1 for d in without_days if d < 1)

    result = {
        "with": {"n": len(with_signal), "medianDays": round(w_med, 3) if w_med else None,
                 "sameDayPct": pct(w_same_day, len(with_days)) if with_days else None},
        "without": {"n": len(without_signal), "medianDays": round(wo_med, 3) if wo_med else None,
                    "sameDayPct": pct(wo_same_day, len(without_days)) if without_days else None},
        "deltaPct": delta_pct,
    }
    print(f"  {name}:")
    print(f"    With: n={result['with']['n']}, med={result['with']['medianDays']}d, same-day={result['with']['sameDayPct']}%")
    print(f"    Without: n={result['without']['n']}, med={result['without']['medianDays']}d, same-day={result['without']['sameDayPct']}%")
    print(f"    Delta: {delta_pct}%")
    return result

# All community issues
print("\n--- All community (closed) ---")
signals_all = {
    "hasCodeBlock": analyze_signal("Code block", lambda i: i["hasCodeBlock"]),
    "hasErrorOutput": analyze_signal("Error output", lambda i: i["hasErrorOutput"]),
    "hasRunLink": analyze_signal("Run link", lambda i: i["hasRunLink"]),
    "hasFilePath": analyze_signal("File path", lambda i: i["hasFilePath"]),
    "hasProposedCode": analyze_signal("Proposed code", lambda i: i["hasProposedCode"]),
    "hasSuggestedFix": analyze_signal("Suggested fix language", lambda i: i["hasSuggestedFix"]),
    "hasReproSteps": analyze_signal("Repro steps", lambda i: i["hasReproSteps"]),
}

# Category breakdown
print("\n--- By category (closed) ---")
category_analysis = {}
for cat in ["doc", "bug", "enhancement", "uncategorized"]:
    cat_closed = [i for i in closed if i["category"] == cat]
    cat_all = [i for i in community if i["category"] == cat]
    days = [i["daysToClose"] for i in cat_closed]
    same_day = sum(1 for d in days if d < 1)

    copilot = sum(1 for i in cat_all if i["copilotDispatched"])

    category_analysis[cat] = {
        "total": len(cat_all),
        "closed": len(cat_closed),
        "open": len(cat_all) - len(cat_closed),
        "closeRate": pct(len(cat_closed), len(cat_all)),
        "medianDays": round(safe_median(days), 3) if days else None,
        "meanDays": round(safe_mean(days), 3) if days else None,
        "sameDayPct": pct(same_day, len(days)) if days else None,
        "copilotDispatchPct": pct(copilot, len(cat_all)),
    }
    print(f"  {cat}: n={len(cat_all)}, closed={len(cat_closed)}, med={category_analysis[cat]['medianDays']}d, same-day={category_analysis[cat]['sameDayPct']}%, copilot={category_analysis[cat]['copilotDispatchPct']}%")

# Bugs only - controlled analysis
print("\n--- Bugs only (closed) ---")
bugs_closed = [i for i in closed if i["category"] == "bug"]
signals_bugs = {}
if bugs_closed:
    signals_bugs = {
        "hasErrorOutput": analyze_signal("Error output (bugs)", lambda i: i["hasErrorOutput"], bugs_closed),
        "hasRunLink": analyze_signal("Run link (bugs)", lambda i: i["hasRunLink"], bugs_closed),
        "hasCodeBlock": analyze_signal("Code block (bugs)", lambda i: i["hasCodeBlock"], bugs_closed),
        "hasFilePath": analyze_signal("File path (bugs)", lambda i: i["hasFilePath"], bugs_closed),
        "hasProposedCode": analyze_signal("Proposed code (bugs)", lambda i: i["hasProposedCode"], bugs_closed),
    }

# Scope analysis
print("\n--- Scope (file paths referenced, closed) ---")
scope_analysis = {}
for bucket, low, high in [("none", 0, 0), ("narrow", 1, 2), ("medium", 3, 5), ("wide", 6, 100)]:
    in_bucket = [i for i in closed if low <= i["filePathCount"] <= high]
    days = [i["daysToClose"] for i in in_bucket]
    same_day = sum(1 for d in days if d < 1)
    scope_analysis[bucket] = {
        "n": len(in_bucket),
        "medianDays": round(safe_median(days), 3) if days else None,
        "sameDayPct": pct(same_day, len(days)) if days else None,
    }
    print(f"  {bucket} ({low}-{high} files): n={len(in_bucket)}, med={scope_analysis[bucket]['medianDays']}d, same-day={scope_analysis[bucket]['sameDayPct']}%")

# Body length buckets
print("\n--- Body length (closed) ---")
length_analysis = {}
for bucket, low, high in [("tiny", 0, 500), ("short", 501, 1500), ("medium", 1501, 3000), ("long", 3001, 6000), ("very_long", 6001, 999999)]:
    in_bucket = [i for i in closed if low <= i["bodyLength"] <= high]
    days = [i["daysToClose"] for i in in_bucket]
    same_day = sum(1 for d in days if d < 1)
    length_analysis[bucket] = {
        "n": len(in_bucket),
        "medianDays": round(safe_median(days), 3) if days else None,
        "sameDayPct": pct(same_day, len(days)) if days else None,
    }
    print(f"  {bucket} ({low}-{high} chars): n={len(in_bucket)}, med={length_analysis[bucket]['medianDays']}d, same-day={length_analysis[bucket]['sameDayPct']}%")

controllable = {
    "signals_all": signals_all,
    "signals_bugs": signals_bugs,
    "category": category_analysis,
    "scope": scope_analysis,
    "length": length_analysis,
}

# ============================================================
# 4.4: Decision-free threshold
# ============================================================
print(f"\n{'=' * 60}")
print("4.4: DECISION-FREE THRESHOLD")
print("=" * 60)

# Classify as decision-free: doc + bug with narrow scope, vs design-required: enhancement + wide scope bugs
decision_free = [i for i in closed if i["category"] in ("doc",) or
                 (i["category"] in ("bug", "uncategorized") and i["filePathCount"] <= 2)]
decision_required = [i for i in closed if i["category"] == "enhancement" or
                     i["filePathCount"] > 2]

df_days = [i["daysToClose"] for i in decision_free]
dr_days = [i["daysToClose"] for i in decision_required]

df_same_day = sum(1 for d in df_days if d < 1)
dr_same_day = sum(1 for d in dr_days if d < 1)

threshold = {
    "decision_free": {
        "n": len(decision_free),
        "medianDays": round(safe_median(df_days), 3) if df_days else None,
        "meanDays": round(safe_mean(df_days), 3) if df_days else None,
        "sameDayPct": pct(df_same_day, len(df_days)),
    },
    "decision_required": {
        "n": len(decision_required),
        "medianDays": round(safe_median(dr_days), 3) if dr_days else None,
        "meanDays": round(safe_mean(dr_days), 3) if dr_days else None,
        "sameDayPct": pct(dr_same_day, len(dr_days)),
    },
    "distributions": {
        "decision_free": sorted(df_days),
        "decision_required": sorted(dr_days),
    }
}

print(f"Decision-free: n={threshold['decision_free']['n']}, med={threshold['decision_free']['medianDays']}d, same-day={threshold['decision_free']['sameDayPct']}%")
print(f"Decision-required: n={threshold['decision_required']['n']}, med={threshold['decision_required']['medianDays']}d, same-day={threshold['decision_required']['sameDayPct']}%")

# ============================================================
# 4.5: What reporters can't control
# ============================================================
print(f"\n{'=' * 60}")
print("4.5: WHAT REPORTERS CAN'T CONTROL")
print("=" * 60)

# Copilot dispatch effect
dispatched = [i for i in closed if i["copilotDispatched"]]
not_dispatched = [i for i in closed if not i["copilotDispatched"]]

disp_days = [i["daysToClose"] for i in dispatched]
no_disp_days = [i["daysToClose"] for i in not_dispatched]

print(f"Copilot dispatched: n={len(dispatched)}, med={round(safe_median(disp_days), 3) if disp_days else None}d")
print(f"Not dispatched: n={len(not_dispatched)}, med={round(safe_median(no_disp_days), 3) if no_disp_days else None}d")

# Reporter frequency effect
author_issues = Counter(i["author"] for i in community)
frequent = {a for a, c in author_issues.items() if c >= 5}
infrequent = {a for a, c in author_issues.items() if c < 5}

freq_closed = [i for i in closed if i["author"] in frequent]
infreq_closed = [i for i in closed if i["author"] in infrequent]

freq_days = [i["daysToClose"] for i in freq_closed]
infreq_days = [i["daysToClose"] for i in infreq_closed]

print(f"\nFrequent filers (5+ issues): n={len(freq_closed)}, med={round(safe_median(freq_days), 3) if freq_days else None}d")
print(f"Infrequent filers (<5): n={len(infreq_closed)}, med={round(safe_median(infreq_days), 3) if infreq_days else None}d")

uncontrollable = {
    "copilot_dispatch": {
        "dispatched": {"n": len(dispatched), "medianDays": round(safe_median(disp_days), 3) if disp_days else None},
        "not_dispatched": {"n": len(not_dispatched), "medianDays": round(safe_median(no_disp_days), 3) if no_disp_days else None},
    },
    "reporter_frequency": {
        "frequent": {"n": len(freq_closed), "medianDays": round(safe_median(freq_days), 3) if freq_days else None,
                     "authors": len(frequent)},
        "infrequent": {"n": len(infreq_closed), "medianDays": round(safe_median(infreq_days), 3) if infreq_days else None,
                       "authors": len(infrequent)},
    },
}

# ============================================================
# 4.6: Contributor archetypes
# ============================================================
print(f"\n{'=' * 60}")
print("4.6: CONTRIBUTOR ARCHETYPES")
print("=" * 60)

# Build per-author profiles (anonymized for the post)
author_profiles = []
for author, count in author_issues.most_common():
    if count < 3:
        continue
    author_issues_list = [i for i in community if i["author"] == author]
    author_closed = [i for i in author_issues_list if i["state"] == "CLOSED" and i["daysToClose"] is not None]
    days = [i["daysToClose"] for i in author_closed]
    body_lens = [i["bodyLength"] for i in author_issues_list]
    categories = Counter(i["category"] for i in author_issues_list)
    copilot = sum(1 for i in author_issues_list if i["copilotDispatched"])

    profile = {
        "author": author,
        "totalIssues": count,
        "closed": len(author_closed),
        "open": count - len(author_closed),
        "closeRate": pct(len(author_closed), count),
        "medianDays": round(safe_median(days), 3) if days else None,
        "avgBodyLength": round(safe_mean(body_lens)) if body_lens else None,
        "categories": dict(categories),
        "copilotDispatched": copilot,
        "copilotRate": pct(copilot, count),
    }
    author_profiles.append(profile)
    print(f"  @{author}: {count} issues, {profile['closeRate']}% close, med={profile['medianDays']}d, avg body={profile['avgBodyLength']} chars, copilot={profile['copilotRate']}%")

# ============================================================
# PR linkage analysis
# ============================================================
print(f"\n{'=' * 60}")
print("PR LINKAGE ANALYSIS")
print("=" * 60)

linkages = linkage_data["linkages"]
merged = [l for l in linkages if l["prMergedAt"]]
bot_prs = [l for l in merged if l["prAuthorIsBot"]]

print(f"Issues with linked PRs: {linkage_data['summary']['issues_with_linked_prs']} / {linkage_data['summary']['community_issues_total']}")
print(f"Merged fix PRs: {len(merged)}")
print(f"Bot-authored: {len(bot_prs)} ({pct(len(bot_prs), len(merged))}%)")

# Implementation time
issue_to_pr = [l["issueToprDays"] for l in merged if l["issueToprDays"] is not None and l["issueToprDays"] >= 0]
pr_to_merge = [l["prToMergeDays"] for l in merged if l["prToMergeDays"] is not None]
issue_to_merge = [l["issueToMergeDays"] for l in merged if l["issueToMergeDays"] is not None and l["issueToMergeDays"] >= 0]

pr_analysis = {
    "linked_issues": linkage_data["summary"]["issues_with_linked_prs"],
    "total_community": linkage_data["summary"]["community_issues_total"],
    "merged_prs": len(merged),
    "bot_authored_pct": pct(len(bot_prs), len(merged)),
    "issue_to_pr_median_days": round(safe_median(issue_to_pr), 3) if issue_to_pr else None,
    "pr_to_merge_median_days": round(safe_median(pr_to_merge), 3) if pr_to_merge else None,
    "issue_to_merge_median_days": round(safe_median(issue_to_merge), 3) if issue_to_merge else None,
    "same_day_merge_pct": pct(sum(1 for d in issue_to_merge if d < 1), len(issue_to_merge)) if issue_to_merge else None,
}

print(f"Issue → PR median: {pr_analysis['issue_to_pr_median_days']} days")
print(f"PR → Merge median: {pr_analysis['pr_to_merge_median_days']} days")
print(f"Issue → Merge median: {pr_analysis['issue_to_merge_median_days']} days")
print(f"Same-day merge: {pr_analysis['same_day_merge_pct']}%")

# Who implements
implementers = Counter(l["prAuthor"] for l in merged)
print(f"\nImplementers:")
for impl, count in implementers.most_common(5):
    print(f"  @{impl}: {count} ({pct(count, len(merged))}%)")

# Who merges
mergers = Counter(l["prMergedBy"] for l in merged if l["prMergedBy"])
print(f"\nMergers:")
for merger, count in mergers.most_common(5):
    print(f"  @{merger}: {count} ({pct(count, len(merged))}%)")

# ============================================================
# Compile all results
# ============================================================
results = {
    "composition": composition,
    "intake_paths": intake_paths,
    "controllable": controllable,
    "threshold": {k: v for k, v in threshold.items() if k != "distributions"},
    "threshold_distributions": threshold["distributions"],
    "uncontrollable": uncontrollable,
    "archetypes": author_profiles,
    "pr_analysis": pr_analysis,
    "pr_implementers": dict(implementers.most_common()),
    "pr_mergers": dict(mergers.most_common()),
}

with open(PROC / "analysis-results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\n{'=' * 60}")
print(f"SAVED: {PROC / 'analysis-results.json'}")
print("=" * 60)
