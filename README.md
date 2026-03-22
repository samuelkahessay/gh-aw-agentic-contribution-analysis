# gh-aw Agentic Contribution Analysis

Empirical analysis of community contribution patterns on [github/gh-aw](https://github.com/github/gh-aw) — the first major open-source repository where agents implement most fixes.

**Companion to ["The Agent Interface"](https://skahessay.dev/posts/the-agent-interface)** by [Sam Kahessay](https://github.com/samuelkahessay).

## What This Is

When you file an issue on an agentic repo, you're not requesting human labor — you're describing work to a machine. This repo contains the data, methodology, and analysis behind the question: **what makes that work agent-compatible?**

## Dataset

- **7,683 total issues** on github/gh-aw
- **6,592 bot-filed** (86%) — smoke tests, triage reports, audits
- **297 community-labeled** (external humans from 114+ contributors)
- **~48 maintainer-filed** (internal, identified by PR merge rights)
- **All PRs** with author, reviewer, merge data, linked issues
- **All releases** with notes, dates, credited issues

## Key Findings

See the full analysis in the [blog post](https://skahessay.dev/posts/the-agent-interface). Headlines:

1. The platform is 86% agent-generated — human issues enter a system built by and for agents
2. Community issues pass through an automated intake pipeline before a human sees them
3. Category framing (bug vs enhancement) is the strongest lever reporters control
4. Run links (`actions/runs/`) reduce median resolution time by 82%
5. Proposed code *inversely* correlates with speed — it's a proxy for complexity
6. The "decision-free threshold" is binary — the agent can or can't fix it without human judgment
7. Issue-side quality metrics are an open opportunity for agentic platforms

## Reproduce It

```bash
# Pull the raw data
./scripts/pull-issues.sh

# Classify authors
python scripts/classify-authors.py

# Extract signals from issue bodies
python scripts/extract-signals.py

# Classify issue categories
python scripts/classify-categories.py

# Link issues to PRs and releases
python scripts/link-prs.py

# Run the full analysis
python scripts/analyze.py

# Generate charts
python scripts/generate-charts.py
```

## Validation

`validation/hand-classified-sample.csv` contains 50 randomly selected issues classified by hand. `validation/validation-report.md` compares automated vs manual classification accuracy.

## Structure

```
data/
  raw/              # Raw JSON from GitHub API
  processed/        # Cleaned, classified datasets
scripts/            # All data collection and analysis scripts
validation/         # Hand-classified validation sample
charts/             # Generated chart assets
findings/           # Per-finding detailed writeups
```

## License

MIT

## Context

This analysis grew out of contributing to gh-aw as a community member. Over the course of building [prd-to-prod](https://github.com/samuelkahessay/prd-to-prod), an autonomous software pipeline on top of gh-aw, I filed 23 issues and had 23 fixes shipped. That experience led to ["The New OSS"](https://skahessay.dev/posts/the-new-oss) — a qualitative essay about how diagnosis is replacing coding as the bottleneck skill. This repo is the quantitative follow-up.
