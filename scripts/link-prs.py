#!/usr/bin/env python3
"""
Link community issues to fix PRs using high-confidence closing references only.

This script intentionally prefers precision over recall. It only accepts GitHub's
native closing phrases such as "fixes #123" or "closes #123" found in PR bodies
or titles. Plain "#123" mentions are excluded because they generate too many
false positives in gh-aw.
"""
import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

RAW = Path(__file__).parent.parent / "data" / "raw"
PROC = Path(__file__).parent.parent / "data" / "processed"

with open(RAW / "all-prs.json") as f:
    prs = json.load(f)

with open(PROC / "community-signals.json") as f:
    signals = json.load(f)

community_issues = {i["number"]: i for i in signals["community_issues"]}

# --- Build PR → issue linkage ---
CLOSE_PATTERN = re.compile(r"(?i)(?:fix(?:es)?|close[sd]?|resolve[sd]?)\s+#(\d+)")

issue_to_prs = defaultdict(list)
excluded_negative_links = 0

for pr in prs:
    body = pr.get("body") or ""
    title = pr.get("title") or ""
    text = body + " " + title

    for match in CLOSE_PATTERN.finditer(text):
        issue_num = int(match.group(1))
        if issue_num in community_issues:
            issue_created = community_issues[issue_num].get("createdAt")
            pr_created = pr.get("createdAt")

            if issue_created and pr_created:
                issue_dt = datetime.fromisoformat(issue_created.replace("Z", "+00:00"))
                pr_dt = datetime.fromisoformat(pr_created.replace("Z", "+00:00"))
                if pr_dt < issue_dt:
                    excluded_negative_links += 1
                    continue

            if not any(existing["number"] == pr["number"] for existing in issue_to_prs[issue_num]):
                issue_to_prs[issue_num].append(pr)

# --- Enrich linkage data ---
BOT_AUTHORS = {"app/copilot-swe-agent", "app/github-actions", "dependabot[bot]", "Copilot"}

def is_bot_author(login):
    return login in BOT_AUTHORS or login.endswith("[bot]") or login.startswith("app/")

linkages = []
for issue_num, linked_prs in issue_to_prs.items():
    issue = community_issues[issue_num]

    for pr in linked_prs:
        pr_author = pr.get("author", {}).get("login", "unknown")
        pr_created = pr.get("createdAt")
        pr_merged = pr.get("mergedAt")
        issue_created = issue.get("createdAt")

        # Time calculations
        issue_to_pr_days = None
        pr_to_merge_days = None
        issue_to_merge_days = None

        if issue_created and pr_created:
            try:
                ic = datetime.fromisoformat(issue_created.replace("Z", "+00:00"))
                pc = datetime.fromisoformat(pr_created.replace("Z", "+00:00"))
                issue_to_pr_days = (pc - ic).total_seconds() / 86400
            except (ValueError, TypeError):
                pass

        if pr_created and pr_merged:
            try:
                pc = datetime.fromisoformat(pr_created.replace("Z", "+00:00"))
                pm = datetime.fromisoformat(pr_merged.replace("Z", "+00:00"))
                pr_to_merge_days = (pm - pc).total_seconds() / 86400
            except (ValueError, TypeError):
                pass

        if issue_created and pr_merged:
            try:
                ic = datetime.fromisoformat(issue_created.replace("Z", "+00:00"))
                pm = datetime.fromisoformat(pr_merged.replace("Z", "+00:00"))
                issue_to_merge_days = (pm - ic).total_seconds() / 86400
            except (ValueError, TypeError):
                pass

        merger = pr.get("mergedBy", {}).get("login") if pr.get("mergedBy") else None

        linkages.append({
            "issueNumber": issue_num,
            "issueTitle": issue["title"],
            "issueAuthor": issue["author"],
            "issueCategory": issue["category"],
            "issueCreatedAt": issue_created,
            "prNumber": pr["number"],
            "prTitle": pr.get("title", ""),
            "prAuthor": pr_author,
            "prAuthorIsBot": is_bot_author(pr_author),
            "prState": pr.get("state", ""),
            "prCreatedAt": pr_created,
            "prMergedAt": pr_merged,
            "prMergedBy": merger,
            "additions": pr.get("additions", 0),
            "deletions": pr.get("deletions", 0),
            "changedFiles": pr.get("changedFiles", 0),
            "linkageMethod": "explicit_closing_reference",
            "issueToprDays": round(issue_to_pr_days, 4) if issue_to_pr_days is not None else None,
            "prToMergeDays": round(pr_to_merge_days, 4) if pr_to_merge_days is not None else None,
            "issueToMergeDays": round(issue_to_merge_days, 4) if issue_to_merge_days is not None else None,
        })

# --- Summary ---
linked_issues = set(l["issueNumber"] for l in linkages)
merged_linkages = [l for l in linkages if l["prMergedAt"]]
bot_authored_prs = [l for l in merged_linkages if l["prAuthorIsBot"]]

print(f"=== Issue → PR Linkage ===")
print(f"  Community issues with linked PRs: {len(linked_issues)} / {len(community_issues)}")
print(f"  Total linkages: {len(linkages)}")
print(f"  Merged linkages: {len(merged_linkages)}")
print(f"  Excluded negative-time links: {excluded_negative_links}")
print(f"  Bot-authored merged PRs: {len(bot_authored_prs)} ({len(bot_authored_prs)*100/len(merged_linkages) if merged_linkages else 0:.1f}%)")

if merged_linkages:
    # Issue to merge time
    times = [l["issueToMergeDays"] for l in merged_linkages if l["issueToMergeDays"] is not None]
    if times:
        times.sort()
        print(f"\n=== Issue → Merge Time (merged PRs) ===")
        print(f"  Median: {times[len(times)//2]:.2f} days")
        print(f"  Mean: {sum(times)/len(times):.2f} days")
        same_day = sum(1 for t in times if t < 1)
        print(f"  Same-day: {same_day} ({same_day*100/len(times):.1f}%)")

    # PR to merge time (agent implementation + review speed)
    pr_times = [l["prToMergeDays"] for l in merged_linkages if l["prToMergeDays"] is not None]
    if pr_times:
        pr_times.sort()
        print(f"\n=== PR → Merge Time (review speed) ===")
        print(f"  Median: {pr_times[len(pr_times)//2]:.2f} days")
        print(f"  Mean: {sum(pr_times)/len(pr_times):.2f} days")

    # Lines changed
    additions = [l["additions"] for l in merged_linkages]
    deletions = [l["deletions"] for l in merged_linkages]
    print(f"\n=== Code Changes (merged PRs) ===")
    print(f"  Median additions: {sorted(additions)[len(additions)//2]}")
    print(f"  Median deletions: {sorted(deletions)[len(deletions)//2]}")
    print(f"  Median files changed: {sorted([l['changedFiles'] for l in merged_linkages])[len(merged_linkages)//2]}")

# PR authors
from collections import Counter
pr_author_counts = Counter(l["prAuthor"] for l in merged_linkages)
print(f"\n=== Who Implements Community Fixes (merged PRs) ===")
for author, count in pr_author_counts.most_common(10):
    pct = count * 100 / len(merged_linkages)
    print(f"  @{author}: {count} ({pct:.1f}%)")

# Who merges
merger_counts = Counter(l["prMergedBy"] for l in merged_linkages if l["prMergedBy"])
print(f"\n=== Who Merges Community Fixes ===")
for merger, count in merger_counts.most_common(10):
    pct = count * 100 / len(merged_linkages)
    print(f"  @{merger}: {count} ({pct:.1f}%)")

# --- Output ---
output = {
    "linkages": linkages,
    "summary": {
        "confidence": "high",
        "method": "explicit closing references only",
        "community_issues_total": len(community_issues),
        "issues_with_linked_prs": len(linked_issues),
        "total_linkages": len(linkages),
        "merged_linkages": len(merged_linkages),
        "bot_authored_merged": len(bot_authored_prs),
        "excluded_negative_links": excluded_negative_links,
    }
}

with open(PROC / "issue-pr-linkage.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"\nSaved to {PROC / 'issue-pr-linkage.json'}")
