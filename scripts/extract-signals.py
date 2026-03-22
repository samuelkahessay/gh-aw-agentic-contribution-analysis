#!/usr/bin/env python3
"""
Extract quality signals and classify categories for all community issues.

Signals extracted from issue body:
- hasCodeBlock: contains ``` fenced code
- hasErrorOutput: contains error messages, stack traces, exit codes
- hasRunLink: contains actions/runs/ URL
- hasFilePath: references source files (.go, .ts, .js, .yaml, .json)
- hasLineNumber: references file:linenum pattern
- hasProposedCode: contains code in diff/go/yaml/typescript blocks
- hasSuggestedFix: uses fix/solution/workaround language
- bodyLength: character count

Category classification:
- doc: documentation label or doc-related title
- bug: bug label
- enhancement: enhancement or feature-request label
- uncategorized: no matching label

Copilot dispatch detection:
- copilotDispatched: any comment contains @copilot

Outputs: data/processed/community-signals.json
"""
import json
import re
from pathlib import Path
from datetime import datetime

RAW = Path(__file__).parent.parent / "data" / "raw"
PROC = Path(__file__).parent.parent / "data" / "processed"
PROC.mkdir(parents=True, exist_ok=True)

with open(RAW / "all-issues.json") as f:
    issues = json.load(f)

with open(PROC / "author-classification.json") as f:
    author_data = json.load(f)

authors = author_data["authors"]

# --- Signal extraction patterns ---
CODE_BLOCK = re.compile(r"```")
ERROR_OUTPUT = re.compile(r"(?i)(error[: ]|failed|ENOENT|EACCES|exit code|stderr|panic|Cannot |fatal |exception|stack trace)")
RUN_LINK = re.compile(r"actions/runs/")
FILE_PATH = re.compile(r"[a-zA-Z_/]+\.(go|ts|js|yaml|yml|json|cjs|mjs)")
LINE_NUMBER = re.compile(r"\.(go|ts|js|cjs):\d+")
PROPOSED_CODE = re.compile(r"```(diff|go|typescript|yaml|javascript|ts|js)")
SUGGESTED_FIX = re.compile(r"(?i)(suggest|fix|solution|workaround|proposed|could be|should be|instead of)")
REPRO_STEPS = re.compile(r"(?i)(repro|steps to|how to reproduce|to reproduce)")

def extract_signals(issue):
    body = issue.get("body") or ""
    title = issue.get("title") or ""
    labels = [l.get("name", "") for l in issue.get("labels", [])]
    comments = issue.get("comments", [])

    # Category
    if "documentation" in labels or re.search(r"(?i)(doc[s ]|typo|readme|example|clarif)", title):
        category = "doc"
    elif "enhancement" in labels or "feature-request" in labels:
        category = "enhancement"
    elif "bug" in labels:
        category = "bug"
    else:
        category = "uncategorized"

    # Copilot dispatch
    copilot_dispatched = any(
        "@copilot" in (c.get("body") or "")
        for c in comments
    )

    # Time calculations
    created = issue.get("createdAt")
    closed = issue.get("closedAt")
    days_to_close = None
    if created and closed:
        try:
            c = datetime.fromisoformat(created.replace("Z", "+00:00"))
            d = datetime.fromisoformat(closed.replace("Z", "+00:00"))
            days_to_close = (d - c).total_seconds() / 86400
        except (ValueError, TypeError):
            pass

    # Time to first label (intake speed)
    # Labels don't have timestamps in our data, so we'll approximate
    # by checking if the issue was labeled at all
    has_any_label = len(labels) > 0

    # File path count (scope proxy)
    file_paths = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_/.-]+\.(go|ts|js|yaml|yml|json|cjs|mjs)", body))

    return {
        "number": issue["number"],
        "title": title,
        "author": issue.get("author", {}).get("login", "unknown"),
        "state": issue.get("state", ""),
        "createdAt": created,
        "closedAt": closed,
        "daysToClose": round(days_to_close, 4) if days_to_close is not None else None,
        "bodyLength": len(body),
        "category": category,
        "labels": labels,
        "commentCount": len(comments),
        "copilotDispatched": copilot_dispatched,
        "hasAnyLabel": has_any_label,
        # Body signals
        "hasCodeBlock": bool(CODE_BLOCK.search(body)),
        "hasErrorOutput": bool(ERROR_OUTPUT.search(body)),
        "hasRunLink": bool(RUN_LINK.search(body)),
        "hasFilePath": bool(FILE_PATH.search(body)),
        "hasLineNumber": bool(LINE_NUMBER.search(body)),
        "hasProposedCode": bool(PROPOSED_CODE.search(body)),
        "hasSuggestedFix": bool(SUGGESTED_FIX.search(body)),
        "hasReproSteps": bool(REPRO_STEPS.search(body)),
        "filePathCount": len(file_paths),
        # Composite scores
        "qualityScore": sum([
            bool(CODE_BLOCK.search(body)),
            bool(ERROR_OUTPUT.search(body)),
            bool(FILE_PATH.search(body)),
            bool(LINE_NUMBER.search(body)),
            bool(RUN_LINK.search(body)),
            bool(PROPOSED_CODE.search(body)),
        ]),
    }


# --- Process community issues ---
community_issues = []
maintainer_issues = []
bot_issues_summary = {"count": 0, "by_month": {}}

for issue in issues:
    login = issue.get("author", {}).get("login", "unknown")
    role = authors.get(login, {}).get("role", "unknown")

    if role == "community":
        community_issues.append(extract_signals(issue))
    elif role == "maintainer":
        maintainer_issues.append(extract_signals(issue))
    elif role == "bot":
        bot_issues_summary["count"] += 1
        created = issue.get("createdAt", "")[:7]  # YYYY-MM
        bot_issues_summary["by_month"][created] = bot_issues_summary["by_month"].get(created, 0) + 1

# --- Summary stats ---
print(f"=== Signal Extraction ===")
print(f"Community issues processed: {len(community_issues)}")
print(f"Maintainer issues processed: {len(maintainer_issues)}")
print(f"Bot issues counted: {bot_issues_summary['count']}")

# Community signal distribution
print(f"\n=== Community Signal Distribution ===")
for signal in ["hasCodeBlock", "hasErrorOutput", "hasRunLink", "hasFilePath",
               "hasLineNumber", "hasProposedCode", "hasSuggestedFix", "hasReproSteps"]:
    count = sum(1 for i in community_issues if i[signal])
    pct = count * 100 / len(community_issues) if community_issues else 0
    print(f"  {signal}: {count} ({pct:.1f}%)")

print(f"\n=== Community Category Distribution ===")
from collections import Counter
cats = Counter(i["category"] for i in community_issues)
for cat, count in cats.most_common():
    pct = count * 100 / len(community_issues)
    print(f"  {cat}: {count} ({pct:.1f}%)")

print(f"\n=== Community Resolution ===")
closed = [i for i in community_issues if i["state"] == "CLOSED"]
open_issues = [i for i in community_issues if i["state"] == "OPEN"]
print(f"  Closed: {len(closed)} ({len(closed)*100/len(community_issues):.1f}%)")
print(f"  Open: {len(open_issues)} ({len(open_issues)*100/len(community_issues):.1f}%)")
if closed:
    days = [i["daysToClose"] for i in closed if i["daysToClose"] is not None]
    if days:
        days.sort()
        print(f"  Median days to close: {days[len(days)//2]:.2f}")
        print(f"  Mean days to close: {sum(days)/len(days):.2f}")
        same_day = sum(1 for d in days if d < 1)
        print(f"  Same-day resolution: {same_day} ({same_day*100/len(days):.1f}%)")

copilot = sum(1 for i in community_issues if i["copilotDispatched"])
print(f"  Copilot dispatched: {copilot} ({copilot*100/len(community_issues):.1f}%)")

# --- Issues by month (for timeline chart) ---
community_by_month = {}
maintainer_by_month = {}
for i in community_issues:
    month = (i.get("createdAt") or "")[:7]
    community_by_month[month] = community_by_month.get(month, 0) + 1
for i in maintainer_issues:
    month = (i.get("createdAt") or "")[:7]
    maintainer_by_month[month] = maintainer_by_month.get(month, 0) + 1

# --- Output ---
output = {
    "community_issues": community_issues,
    "maintainer_issues": maintainer_issues,
    "bot_summary": bot_issues_summary,
    "timeline": {
        "community_by_month": dict(sorted(community_by_month.items())),
        "maintainer_by_month": dict(sorted(maintainer_by_month.items())),
        "bot_by_month": dict(sorted(bot_issues_summary["by_month"].items())),
    },
    "summary": {
        "community_count": len(community_issues),
        "maintainer_count": len(maintainer_issues),
        "bot_count": bot_issues_summary["count"],
        "total": len(issues),
    }
}

with open(PROC / "community-signals.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"\nSaved to {PROC / 'community-signals.json'}")
