#!/usr/bin/env python3
"""
Link community issues to fix PRs using the GitHub Timeline API.

This script uses the `connected` and `cross-referenced` events from each
issue's timeline, which capture GitHub's native issue-PR linkage — the same
connection visible in the UI sidebar. This is higher recall than parsing
PR body text for closing keywords.

Rate-limited: one API call per issue. For 435 issues, expect ~5-7 minutes.

Outputs: data/processed/issue-pr-linkage.json (replaces previous version)
"""
import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

PROC = Path(__file__).parent.parent / "data" / "processed"
RAW = Path(__file__).parent.parent / "data" / "raw"

with open(PROC / "community-signals.json") as f:
    signals = json.load(f)

with open(RAW / "all-prs.json") as f:
    all_prs = {pr["number"]: pr for pr in json.load(f)}

community_issues = signals["community_issues"]
closed_issues = [i for i in community_issues if i["state"] == "CLOSED"]

print(f"=== Timeline-based PR Linkage ===")
print(f"Community issues (closed): {len(closed_issues)}")
print(f"Community issues (total): {len(community_issues)}")
print()

BOT_AUTHORS = {"app/copilot-swe-agent", "app/github-actions", "dependabot[bot]", "Copilot"}

def is_bot_author(login):
    return login in BOT_AUTHORS or login.endswith("[bot]") or login.startswith("app/")

def get_timeline(issue_number):
    """Fetch timeline events for an issue via gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/github/gh-aw/issues/{issue_number}/timeline",
             "--jq", "."],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        print(f"  Warning: failed to fetch timeline for #{issue_number}: {e}", file=sys.stderr)
    return []

def extract_pr_numbers(timeline_events):
    """Extract PR numbers from connected/cross-referenced timeline events."""
    pr_numbers = set()
    for event in timeline_events:
        event_type = event.get("event") or event.get("type", "")

        if event_type == "connected":
            # connected events don't always include the PR number directly
            # but the source may contain it
            source = event.get("source", {})
            issue = source.get("issue", {})
            pr = issue.get("pull_request")
            if pr and issue.get("number"):
                pr_numbers.add(issue["number"])

        elif event_type == "cross-referenced":
            source = event.get("source", {})
            issue = source.get("issue", {})
            pr = issue.get("pull_request")
            if pr and issue.get("number"):
                pr_numbers.add(issue["number"])

    return pr_numbers

# Process all closed community issues
linkages = []
issues_with_links = set()
failed_fetches = 0

for idx, issue in enumerate(closed_issues):
    num = issue["number"]
    if idx % 20 == 0:
        print(f"  Processing {idx+1}/{len(closed_issues)} (#{num})...")

    timeline = get_timeline(num)
    if not timeline:
        failed_fetches += 1
        continue

    pr_numbers = extract_pr_numbers(timeline)

    for pr_num in pr_numbers:
        pr = all_prs.get(pr_num)
        if not pr:
            continue

        pr_author = (pr.get("author") or {}).get("login", "unknown")
        pr_created = pr.get("createdAt")
        pr_merged = pr.get("mergedAt")
        merger = (pr.get("mergedBy") or {}).get("login") if pr.get("mergedBy") else None
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
                if issue_to_pr_days < 0:
                    continue  # PR predates issue — not a fix
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
                if issue_to_merge_days < 0:
                    continue
            except (ValueError, TypeError):
                pass

        issues_with_links.add(num)
        linkages.append({
            "issueNumber": num,
            "issueTitle": issue["title"],
            "issueAuthor": issue["author"],
            "issueCategory": issue["category"],
            "issueCreatedAt": issue_created,
            "prNumber": pr_num,
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
            "linkageMethod": "timeline_api",
            "issueToprDays": round(issue_to_pr_days, 4) if issue_to_pr_days is not None else None,
            "prToMergeDays": round(pr_to_merge_days, 4) if pr_to_merge_days is not None else None,
            "issueToMergeDays": round(issue_to_merge_days, 4) if issue_to_merge_days is not None else None,
        })

    # Be nice to the API
    if idx % 10 == 9:
        time.sleep(0.5)

# Summary
merged = [l for l in linkages if l["prMergedAt"]]
bot_prs = [l for l in merged if l["prAuthorIsBot"]]

print(f"\n=== Results ===")
print(f"Issues processed: {len(closed_issues)}")
print(f"Failed API fetches: {failed_fetches}")
print(f"Issues with linked PRs: {len(issues_with_links)} / {len(closed_issues)}")
print(f"Total linkages: {len(linkages)}")
print(f"Merged linkages: {len(merged)}")
print(f"Bot-authored merged PRs: {len(bot_prs)} ({len(bot_prs)*100/len(merged) if merged else 0:.1f}%)")

if merged:
    issue_to_merge = [l["issueToMergeDays"] for l in merged if l["issueToMergeDays"] is not None]
    pr_to_merge = [l["prToMergeDays"] for l in merged if l["prToMergeDays"] is not None]

    if issue_to_merge:
        issue_to_merge.sort()
        print(f"\nIssue → Merge median: {issue_to_merge[len(issue_to_merge)//2]:.3f} days")
        same_day = sum(1 for d in issue_to_merge if d < 1)
        print(f"Same-day: {same_day} ({same_day*100/len(issue_to_merge):.1f}%)")

    if pr_to_merge:
        pr_to_merge.sort()
        print(f"PR → Merge median: {pr_to_merge[len(pr_to_merge)//2]:.3f} days")

    # Who implements
    implementers = Counter(l["prAuthor"] for l in merged)
    print(f"\nImplementers:")
    for impl, count in implementers.most_common(10):
        print(f"  @{impl}: {count} ({count*100/len(merged):.1f}%)")

    # Who merges
    mergers = Counter(l["prMergedBy"] for l in merged if l["prMergedBy"])
    print(f"\nMergers:")
    for merger, count in mergers.most_common(10):
        print(f"  @{merger}: {count} ({count*100/len(merged):.1f}%)")

# Output
output = {
    "linkages": linkages,
    "summary": {
        "confidence": "high",
        "method": "GitHub Timeline API (connected + cross-referenced events)",
        "community_issues_total": len(community_issues),
        "closed_issues_processed": len(closed_issues),
        "failed_fetches": failed_fetches,
        "issues_with_linked_prs": len(issues_with_links),
        "total_linkages": len(linkages),
        "merged_linkages": len(merged),
        "bot_authored_merged": len(bot_prs),
    }
}

with open(PROC / "issue-pr-linkage.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"\nSaved to {PROC / 'issue-pr-linkage.json'}")
