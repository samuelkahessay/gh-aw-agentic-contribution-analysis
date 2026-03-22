#!/usr/bin/env python3
"""
Classify all issue and PR authors into: bot, maintainer, community, unknown.

Maintainers identified by:
1. PR merge rights (from pr-mergers.json)
2. PR review comments (from pr-review-comments.json if available)
3. Known bot patterns (app/*, *[bot])

Outputs: data/processed/author-classification.json
"""
import json
import re
from collections import Counter
from pathlib import Path

RAW = Path(__file__).parent.parent / "data" / "raw"
OUT = Path(__file__).parent.parent / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

# --- Load data ---
with open(RAW / "all-issues.json") as f:
    issues = json.load(f)

with open(RAW / "pr-mergers.json") as f:
    mergers = json.load(f)

with open(RAW / "all-prs.json") as f:
    prs = json.load(f)

# --- Identify bots ---
BOT_PATTERNS = [
    re.compile(r"\[bot\]$"),
    re.compile(r"^app/"),
]

def is_bot(login: str) -> bool:
    return any(p.search(login) for p in BOT_PATTERNS)

# --- Identify maintainers by merge rights ---
merge_counts = Counter()
for pr in mergers:
    if pr.get("mergedBy") and pr["mergedBy"].get("login"):
        merge_counts[pr["mergedBy"]["login"]] += 1

# PR authors who are not bots (internal contributors)
pr_authors = Counter()
for pr in prs:
    login = pr.get("author", {}).get("login", "")
    if login and not is_bot(login):
        pr_authors[login] += 1

# Maintainers: anyone who has merged PRs
maintainer_logins = set(merge_counts.keys())

# Also add frequent non-bot PR authors (5+ PRs) as maintainer-adjacent
for login, count in pr_authors.items():
    if count >= 5 and login not in maintainer_logins:
        maintainer_logins.add(login)

# --- Classify all issue authors ---
all_authors = {}
for issue in issues:
    login = issue.get("author", {}).get("login", "unknown")
    if login in all_authors:
        continue

    if is_bot(login):
        role = "bot"
    elif login in maintainer_logins:
        role = "maintainer"
    else:
        # Check if they have the community label on any issue
        has_community = any(
            label.get("name") == "community"
            for i in issues
            if i.get("author", {}).get("login") == login
            for label in i.get("labels", [])
        )
        role = "community" if has_community else "unknown"

    all_authors[login] = {
        "login": login,
        "role": role,
        "merge_count": merge_counts.get(login, 0),
        "pr_count": pr_authors.get(login, 0),
    }

# --- Summary ---
role_counts = Counter(a["role"] for a in all_authors.values())
print("=== Author Classification ===")
for role, count in role_counts.most_common():
    print(f"  {role}: {count}")

print(f"\n=== Maintainers (by merge rights) ===")
for login, count in merge_counts.most_common(10):
    print(f"  @{login}: {count} merges")

# --- Classify issues by author type ---
issue_by_role = Counter()
for issue in issues:
    login = issue.get("author", {}).get("login", "unknown")
    author_info = all_authors.get(login, {"role": "unknown"})
    issue_by_role[author_info["role"]] += 1

print(f"\n=== Issues by Author Role ===")
for role, count in issue_by_role.most_common():
    pct = count * 100 / len(issues)
    print(f"  {role}: {count} ({pct:.1f}%)")

# --- Check community label coverage ---
community_labeled = sum(
    1 for i in issues
    if any(l.get("name") == "community" for l in i.get("labels", []))
)
human_issues = sum(
    1 for i in issues
    if not is_bot(i.get("author", {}).get("login", ""))
)
human_without_community = sum(
    1 for i in issues
    if not is_bot(i.get("author", {}).get("login", ""))
    and not any(l.get("name") == "community" for l in i.get("labels", []))
)

print(f"\n=== Community Label Coverage ===")
print(f"  Total issues: {len(issues)}")
print(f"  Community-labeled: {community_labeled}")
print(f"  Human-filed (non-bot): {human_issues}")
print(f"  Human without community label: {human_without_community}")
print(f"  Community label coverage of human issues: {(community_labeled / human_issues * 100) if human_issues else 0:.1f}%")

# --- Output ---
output = {
    "authors": all_authors,
    "maintainer_logins": sorted(maintainer_logins),
    "merge_counts": dict(merge_counts.most_common()),
    "summary": {
        "total_authors": len(all_authors),
        "roles": dict(role_counts),
        "issues_by_role": dict(issue_by_role),
        "total_issues": len(issues),
        "community_labeled": community_labeled,
        "human_filed": human_issues,
        "human_without_community": human_without_community,
    }
}

with open(OUT / "author-classification.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"\nSaved to {OUT / 'author-classification.json'}")
