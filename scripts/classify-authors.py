#!/usr/bin/env python3
"""
Classify issue authors into objective roles used by the analysis.

Roles:
- bot: login matches GitHub app / bot conventions
- maintainer: account has merged at least one PR into github/gh-aw
- community: every other human issue author

This script intentionally avoids inferring maintainer status from PR volume,
labels, or any other soft signals.
"""
import json
import re
from collections import Counter
from pathlib import Path

RAW = Path(__file__).parent.parent / "data" / "raw"
OUT = Path(__file__).parent.parent / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

with open(RAW / "all-issues.json") as f:
    issues = json.load(f)

with open(RAW / "pr-mergers.json") as f:
    mergers = json.load(f)

with open(RAW / "all-prs.json") as f:
    prs = json.load(f)

BOT_PATTERNS = [
    re.compile(r"\[bot\]$"),
    re.compile(r"^app/"),
]


def is_bot(login: str) -> bool:
    return any(pattern.search(login) for pattern in BOT_PATTERNS)


merge_counts = Counter()
for pr in mergers:
    merged_by = pr.get("mergedBy") or {}
    login = merged_by.get("login")
    if login:
        merge_counts[login] += 1

maintainer_logins = set(merge_counts.keys())

pr_counts = Counter()
for pr in prs:
    login = (pr.get("author") or {}).get("login", "")
    if login and not is_bot(login):
        pr_counts[login] += 1

issue_counts = Counter()
community_label_issue_counts = Counter()
for issue in issues:
    login = (issue.get("author") or {}).get("login", "unknown")
    issue_counts[login] += 1
    if any(label.get("name") == "community" for label in issue.get("labels", [])):
        community_label_issue_counts[login] += 1

authors = {}
for login in issue_counts:
    if is_bot(login):
        role = "bot"
    elif login in maintainer_logins:
        role = "maintainer"
    else:
        role = "community"

    authors[login] = {
        "login": login,
        "role": role,
        "merge_count": merge_counts.get(login, 0),
        "pr_count": pr_counts.get(login, 0),
        "issue_count": issue_counts.get(login, 0),
        "community_labeled_issue_count": community_label_issue_counts.get(login, 0),
    }

role_counts = Counter(author["role"] for author in authors.values())
issue_by_role = Counter()
unlabeled_by_role = Counter()
community_labeled_by_role = Counter()

for issue in issues:
    login = (issue.get("author") or {}).get("login", "unknown")
    role = authors[login]["role"]
    issue_by_role[role] += 1
    if any(label.get("name") == "community" for label in issue.get("labels", [])):
        community_labeled_by_role[role] += 1
    else:
        unlabeled_by_role[role] += 1

community_issues = issue_by_role["community"]
community_labeled_issues = community_labeled_by_role["community"]
community_label_coverage = (
    round(community_labeled_issues * 100 / community_issues, 1)
    if community_issues
    else 0.0
)

print("=== Author Classification ===")
for role, count in role_counts.most_common():
    print(f"  {role}: {count}")

print("\n=== Maintainers (by merged PRs) ===")
for login, count in merge_counts.most_common(10):
    print(f"  @{login}: {count} merges")

print("\n=== Issues by Author Role ===")
for role, count in issue_by_role.most_common():
    pct = count * 100 / len(issues)
    print(f"  {role}: {count} ({pct:.1f}%)")

print("\n=== Community Label Coverage (community role only) ===")
print(f"  Community issues: {community_issues}")
print(f"  Community-labeled: {community_labeled_issues}")
print(f"  Unlabeled: {unlabeled_by_role['community']}")
print(f"  Coverage: {community_label_coverage:.1f}%")

output = {
    "authors": authors,
    "maintainer_logins": sorted(maintainer_logins),
    "merge_counts": dict(merge_counts.most_common()),
    "summary": {
        "total_authors": len(authors),
        "roles": dict(role_counts),
        "issues_by_role": dict(issue_by_role),
        "total_issues": len(issues),
        "community_issues": community_issues,
        "community_contributors": sum(1 for author in authors.values() if author["role"] == "community"),
        "community_labeled_community_issues": community_labeled_issues,
        "community_unlabeled_community_issues": unlabeled_by_role["community"],
        "community_label_coverage_pct": community_label_coverage,
        "community_labeled_by_role": dict(community_labeled_by_role),
        "unlabeled_by_role": dict(unlabeled_by_role),
    },
}

with open(OUT / "author-classification.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"\nSaved to {OUT / 'author-classification.json'}")
