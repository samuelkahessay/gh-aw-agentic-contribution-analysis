#!/usr/bin/env bash
# Pull all issues from github/gh-aw with full metadata
# Requires: gh CLI authenticated with access to github/gh-aw
set -euo pipefail

REPO="github/gh-aw"
RAW_DIR="$(dirname "$0")/../data/raw"
mkdir -p "$RAW_DIR"

echo "=== Pulling all issues (paginated) ==="
gh issue list --repo "$REPO" --state all --limit 10000 \
  --json number,title,author,state,createdAt,closedAt,body,labels,comments,milestone \
  > "$RAW_DIR/all-issues.json"
echo "Issues pulled: $(jq length "$RAW_DIR/all-issues.json")"

echo "=== Pulling all PRs ==="
gh pr list --repo "$REPO" --state all --limit 5000 \
  --json number,title,author,state,createdAt,closedAt,mergedAt,mergedBy,body,labels,reviews,additions,deletions,changedFiles \
  > "$RAW_DIR/all-prs.json"
echo "PRs pulled: $(jq length "$RAW_DIR/all-prs.json")"

echo "=== Pulling all releases ==="
gh release list --repo "$REPO" --limit 100 \
  --json tagName,publishedAt,name,body \
  > "$RAW_DIR/all-releases.json" 2>/dev/null || \
gh api repos/$REPO/releases --paginate --jq '.' > "$RAW_DIR/all-releases.json"
echo "Releases pulled: $(jq length "$RAW_DIR/all-releases.json")"

echo "=== Pulling PR merge authors (maintainer identification) ==="
gh pr list --repo "$REPO" --state merged --limit 5000 \
  --json number,mergedBy \
  > "$RAW_DIR/pr-mergers.json"
echo "Merged PRs: $(jq length "$RAW_DIR/pr-mergers.json")"

echo "=== Pulling PR review comments (reviewer identification) ==="
gh api "repos/$REPO/pulls/comments" --paginate --jq '.' \
  > "$RAW_DIR/pr-review-comments.json" 2>/dev/null || echo "PR comments: paginated API may need manual handling"

echo "=== Done ==="
echo "Raw data saved to $RAW_DIR/"
ls -lh "$RAW_DIR/"
