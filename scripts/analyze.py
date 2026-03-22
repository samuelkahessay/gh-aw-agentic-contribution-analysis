#!/usr/bin/env python3
"""
Roll up processed datasets into publishable descriptive results.

Outputs:
- data/processed/analysis-results.json
- findings/summary.md
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

with open(PROC / "author-classification.json") as f:
    author_data = json.load(f)

with open(PROC / "issue-pr-linkage.json") as f:
    linkage_data = json.load(f)

community = signals["community_issues"]
maintainer = signals["maintainer_issues"]
closed = [issue for issue in community if issue["state"] == "CLOSED" and issue["daysToClose"] is not None]


def pct(numerator, denominator):
    return round(numerator * 100 / denominator, 1) if denominator else 0.0


def safe_median(values):
    return round(median(values), 3) if values else None


def safe_mean(values):
    return round(mean(values), 3) if values else None


def analyze_signal(pool, field):
    with_signal = [issue for issue in pool if issue[field]]
    without_signal = [issue for issue in pool if not issue[field]]
    with_days = [issue["daysToClose"] for issue in with_signal]
    without_days = [issue["daysToClose"] for issue in without_signal]

    delta_pct = None
    if with_days and without_days:
        without_median = median(without_days)
        with_median = median(with_days)
        if without_median > 0:
            delta_pct = round((with_median - without_median) / without_median * 100, 1)

    return {
        "with": {
            "n": len(with_signal),
            "medianDays": safe_median(with_days),
            "sameDayPct": pct(sum(1 for day in with_days if day < 1), len(with_days)),
        },
        "without": {
            "n": len(without_signal),
            "medianDays": safe_median(without_days),
            "sameDayPct": pct(sum(1 for day in without_days if day < 1), len(without_days)),
        },
        "deltaPct": delta_pct,
    }


print("=" * 60)
print("PLATFORM COMPOSITION")
print("=" * 60)

total = signals["summary"]["total"]
bot_count = signals["summary"]["bot_count"]
maintainer_count = signals["summary"]["maintainer_count"]
community_count = signals["summary"]["community_count"]

composition = {
    "total": total,
    "bot": {"count": bot_count, "pct": pct(bot_count, total)},
    "maintainer": {"count": maintainer_count, "pct": pct(maintainer_count, total)},
    "community": {"count": community_count, "pct": pct(community_count, total)},
    "ratio_bot_per_community": round(bot_count / community_count, 1) if community_count else None,
    "timeline": signals["timeline"],
}

print(f"Total issues: {total}")
print(f"Bot issues: {bot_count} ({composition['bot']['pct']}%)")
print(f"Maintainer issues: {maintainer_count} ({composition['maintainer']['pct']}%)")
print(f"Community issues: {community_count} ({composition['community']['pct']}%)")

print("\n" + "=" * 60)
print("LABEL COVERAGE")
print("=" * 60)

coverage_summary = author_data["summary"]
label_coverage = {
    "community_issues": coverage_summary["community_issues"],
    "community_contributors": coverage_summary["community_contributors"],
    "community_labeled_community_issues": coverage_summary["community_labeled_community_issues"],
    "community_unlabeled_community_issues": coverage_summary["community_unlabeled_community_issues"],
    "community_label_coverage_pct": coverage_summary["community_label_coverage_pct"],
}

print(
    "Community label coverage:",
    f"{label_coverage['community_labeled_community_issues']}/{label_coverage['community_issues']}",
    f"({label_coverage['community_label_coverage_pct']}%)",
)

print("\n" + "=" * 60)
print("CATEGORY BREAKDOWN")
print("=" * 60)

category_analysis = {}
for category in ["doc", "bug", "enhancement", "uncategorized"]:
    category_all = [issue for issue in community if issue["category"] == category]
    category_closed = [issue for issue in closed if issue["category"] == category]
    days = [issue["daysToClose"] for issue in category_closed]
    category_analysis[category] = {
        "total": len(category_all),
        "closed": len(category_closed),
        "open": len(category_all) - len(category_closed),
        "closeRate": pct(len(category_closed), len(category_all)),
        "medianDays": safe_median(days),
        "meanDays": safe_mean(days),
        "sameDayPct": pct(sum(1 for day in days if day < 1), len(days)),
        "copilotDispatchPct": pct(
            sum(1 for issue in category_all if issue["copilotDispatched"]),
            len(category_all),
        ),
    }
    print(
        f"{category}:",
        f"n={category_analysis[category]['total']},",
        f"median={category_analysis[category]['medianDays']}d,",
        f"same-day={category_analysis[category]['sameDayPct']}%,",
        f"copilot={category_analysis[category]['copilotDispatchPct']}%",
    )

print("\n" + "=" * 60)
print("SIGNALS")
print("=" * 60)

signals_all = {
    "hasCodeBlock": analyze_signal(closed, "hasCodeBlock"),
    "hasErrorOutput": analyze_signal(closed, "hasErrorOutput"),
    "hasRunLink": analyze_signal(closed, "hasRunLink"),
    "hasFilePath": analyze_signal(closed, "hasFilePath"),
    "hasLineNumber": analyze_signal(closed, "hasLineNumber"),
    "hasProposedCode": analyze_signal(closed, "hasProposedCode"),
    "hasSuggestedFix": analyze_signal(closed, "hasSuggestedFix"),
    "hasReproSteps": analyze_signal(closed, "hasReproSteps"),
}

for name, result in signals_all.items():
    print(
        f"{name}:",
        f"with={result['with']['medianDays']}d,",
        f"without={result['without']['medianDays']}d,",
        f"delta={result['deltaPct']}%",
    )

bugs_closed = [issue for issue in closed if issue["category"] == "bug"]
signals_bugs = {}
if bugs_closed:
    signals_bugs = {
        "hasErrorOutput": analyze_signal(bugs_closed, "hasErrorOutput"),
        "hasRunLink": analyze_signal(bugs_closed, "hasRunLink"),
        "hasFilePath": analyze_signal(bugs_closed, "hasFilePath"),
        "hasProposedCode": analyze_signal(bugs_closed, "hasProposedCode"),
        "hasReproSteps": analyze_signal(bugs_closed, "hasReproSteps"),
    }

print("\n" + "=" * 60)
print("SCOPE AND LENGTH")
print("=" * 60)

scope_analysis = {}
for bucket, low, high in [
    ("none", 0, 0),
    ("narrow", 1, 2),
    ("medium", 3, 5),
    ("wide", 6, 999999),
]:
    bucket_issues = [issue for issue in closed if low <= issue["filePathCount"] <= high]
    days = [issue["daysToClose"] for issue in bucket_issues]
    scope_analysis[bucket] = {
        "n": len(bucket_issues),
        "medianDays": safe_median(days),
        "sameDayPct": pct(sum(1 for day in days if day < 1), len(days)),
    }
    print(
        f"{bucket}:",
        f"n={scope_analysis[bucket]['n']},",
        f"median={scope_analysis[bucket]['medianDays']}d,",
        f"same-day={scope_analysis[bucket]['sameDayPct']}%",
    )

length_analysis = {}
for bucket, low, high in [
    ("tiny", 0, 500),
    ("short", 501, 1500),
    ("medium", 1501, 3000),
    ("long", 3001, 6000),
    ("very_long", 6001, 999999),
]:
    bucket_issues = [issue for issue in closed if low <= issue["bodyLength"] <= high]
    days = [issue["daysToClose"] for issue in bucket_issues]
    length_analysis[bucket] = {
        "n": len(bucket_issues),
        "medianDays": safe_median(days),
        "sameDayPct": pct(sum(1 for day in days if day < 1), len(days)),
    }
    print(
        f"{bucket}:",
        f"n={length_analysis[bucket]['n']},",
        f"median={length_analysis[bucket]['medianDays']}d,",
        f"same-day={length_analysis[bucket]['sameDayPct']}%",
    )

print("\n" + "=" * 60)
print("REPORTER / MAINTAINER FACTORS")
print("=" * 60)

author_issue_counts = Counter(issue["author"] for issue in community)
frequent_authors = {author for author, count in author_issue_counts.items() if count >= 5}
frequent_closed = [issue for issue in closed if issue["author"] in frequent_authors]
infrequent_closed = [issue for issue in closed if issue["author"] not in frequent_authors]

uncontrollable = {
    "copilot_dispatch": {
        "dispatched": analyze_signal(closed, "copilotDispatched")["with"],
        "not_dispatched": analyze_signal(closed, "copilotDispatched")["without"],
    },
    "reporter_frequency": {
        "frequent": {
            "authors": len(frequent_authors),
            "n": len(frequent_closed),
            "medianDays": safe_median([issue["daysToClose"] for issue in frequent_closed]),
        },
        "infrequent": {
            "authors": len(author_issue_counts) - len(frequent_authors),
            "n": len(infrequent_closed),
            "medianDays": safe_median([issue["daysToClose"] for issue in infrequent_closed]),
        },
    },
}

print(
    "Frequent filers:",
    uncontrollable["reporter_frequency"]["frequent"]["n"],
    "closed issues, median",
    uncontrollable["reporter_frequency"]["frequent"]["medianDays"],
    "days",
)
print(
    "Infrequent filers:",
    uncontrollable["reporter_frequency"]["infrequent"]["n"],
    "closed issues, median",
    uncontrollable["reporter_frequency"]["infrequent"]["medianDays"],
    "days",
)

print("\n" + "=" * 60)
print("HIGH-CONFIDENCE PR LINKAGE")
print("=" * 60)

linkages = linkage_data["linkages"]
merged_linkages = [linkage for linkage in linkages if linkage["prMergedAt"]]
implementers = Counter(linkage["prAuthor"] for linkage in merged_linkages)
mergers = Counter(linkage["prMergedBy"] for linkage in merged_linkages if linkage["prMergedBy"])
pr_to_merge_days = [linkage["prToMergeDays"] for linkage in merged_linkages if linkage["prToMergeDays"] is not None]
issue_to_merge_days = [linkage["issueToMergeDays"] for linkage in merged_linkages if linkage["issueToMergeDays"] is not None]

pr_analysis = {
    "confidence": linkage_data["summary"]["confidence"],
    "method": linkage_data["summary"]["method"],
    "linked_issues": linkage_data["summary"]["issues_with_linked_prs"],
    "total_community_issues": linkage_data["summary"]["community_issues_total"],
    "merged_prs": len(merged_linkages),
    "bot_authored_pct": pct(
        linkage_data["summary"]["bot_authored_merged"],
        len(merged_linkages),
    ),
    "pr_to_merge_median_days": safe_median(pr_to_merge_days),
    "issue_to_merge_median_days": safe_median(issue_to_merge_days),
    "implementers": dict(implementers.most_common()),
    "mergers": dict(mergers.most_common()),
}

print(
    f"Linked community issues: {pr_analysis['linked_issues']} / {pr_analysis['total_community_issues']}"
)
print(f"Merged PRs: {pr_analysis['merged_prs']}")
print(f"PR->merge median: {pr_analysis['pr_to_merge_median_days']} days")

author_profiles = []
for author, total_issues in author_issue_counts.most_common():
    if total_issues < 3:
        continue

    author_issues = [issue for issue in community if issue["author"] == author]
    author_closed = [issue for issue in author_issues if issue["state"] == "CLOSED" and issue["daysToClose"] is not None]
    author_profiles.append(
        {
            "author": author,
            "totalIssues": total_issues,
            "closed": len(author_closed),
            "open": total_issues - len(author_closed),
            "closeRate": pct(len(author_closed), total_issues),
            "medianDays": safe_median([issue["daysToClose"] for issue in author_closed]),
            "avgBodyLength": round(mean(issue["bodyLength"] for issue in author_issues)),
            "categories": dict(Counter(issue["category"] for issue in author_issues)),
            "copilotDispatched": sum(1 for issue in author_issues if issue["copilotDispatched"]),
            "copilotRate": pct(
                sum(1 for issue in author_issues if issue["copilotDispatched"]),
                total_issues,
            ),
        }
    )

limitations = [
    'Role classification is conservative: "community" means any non-bot issue author without merge rights in gh-aw.',
    "Category buckets are heuristic label/title groupings used for descriptive analysis, not causal inference.",
    "PR linkage uses explicit closing references only; this is high precision but low recall.",
    "The strongest directional signal appears inside the labeled bug subset, which is materially smaller than the full community sample.",
]

results = {
    "composition": composition,
    "label_coverage": label_coverage,
    "category": category_analysis,
    "signals_all": signals_all,
    "signals_bugs": signals_bugs,
    "scope": scope_analysis,
    "length": length_analysis,
    "uncontrollable": uncontrollable,
    "archetypes": author_profiles,
    "pr_analysis": pr_analysis,
    "limitations": limitations,
}

with open(PROC / "analysis-results.json", "w") as f:
    json.dump(results, f, indent=2)

summary_lines = [
    "# Analysis Summary",
    "",
    "## Sample",
    "",
    f"- Total issues: {composition['total']}",
    f"- Bot-authored issues: {composition['bot']['count']} ({composition['bot']['pct']}%)",
    f"- Maintainer-authored issues: {composition['maintainer']['count']} ({composition['maintainer']['pct']}%)",
    f"- Community issues: {composition['community']['count']} ({composition['community']['pct']}%) from {label_coverage['community_contributors']} contributors",
    f"- Community label coverage on community issues: {label_coverage['community_label_coverage_pct']}%",
    "",
    "## Strongest descriptive patterns",
    "",
    f"- Enhancements have the slowest median closure time: {category_analysis['enhancement']['medianDays']} days.",
    f"- Within labeled bugs, error output shifts median closure time from {signals_bugs['hasErrorOutput']['without']['medianDays']} to {signals_bugs['hasErrorOutput']['with']['medianDays']} days.",
    f"- Body length is weakly informative: medians range from {length_analysis['tiny']['medianDays']} to {length_analysis['very_long']['medianDays']} days across buckets.",
    f"- High-confidence PR linkage exists for {pr_analysis['linked_issues']} community issues ({pct(pr_analysis['linked_issues'], pr_analysis['total_community_issues'])}% of the sample).",
    "",
    "## Limitations",
    "",
]

for limitation in limitations:
    summary_lines.append(f"- {limitation}")

summary_lines.append("")

with open(FINDINGS / "summary.md", "w") as f:
    f.write("\n".join(summary_lines))

print("\nSaved to", PROC / "analysis-results.json")
print("Saved to", FINDINGS / "summary.md")
