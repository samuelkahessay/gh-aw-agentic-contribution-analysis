# gh-aw Agentic Contribution Analysis

Descriptive analysis of contribution patterns on [github/gh-aw](https://github.com/github/gh-aw), with a focus on what makes non-maintainer issue reports easiest to resolve in an agent-heavy repository.

**Companion to ["The Agent Interface"](https://skahessay.dev/posts/the-agent-interface)** by [Sam Kahessay](https://github.com/samuelkahessay).

## What This Is

This repo contains the data pull, heuristics, and rollup scripts behind the essay.

The emphasis is descriptive, not causal:

- author roles are defined conservatively
- issue categories are heuristic label/title buckets
- PR linkage is high precision and low recall

The goal is to make every published number traceable to code and generated artifacts.

## Dataset

- **7,684 total issues** on github/gh-aw
- **6,648 bot-authored issues** (86.5%)
- **601 maintainer-authored issues** (7.8%)
- **435 community issues** from **158** non-maintainer human contributors (5.7%)
- **259 / 435** community issues carry the `community` label (59.5% coverage)
- **13** high-confidence issue → PR links via explicit closing references

## Key Findings

See the full analysis in the [blog post](https://skahessay.dev/posts/the-agent-interface). Current headlines:

1. The repository is overwhelmingly bot-authored by issue volume.
2. The `community` label is incomplete as a sampling frame for non-maintainer issues.
3. Category framing matters more than body length.
4. Within labeled bugs, error output is the strongest helpful signal in the current sample.
5. Repository-native PR linkage is sparse, so PR-side authorship claims need tighter evidence than loose `#N` references.

## Reproduce It

```bash
# Pull the raw data
./scripts/pull-issues.sh

# Classify authors
python3 scripts/classify-authors.py

# Extract signals from issue bodies
python3 scripts/extract-signals.py

# Link issues to PRs
python3 scripts/link-prs.py

# Roll up the analysis
python3 scripts/analyze.py
```

Generated outputs:

- `data/processed/author-classification.json`
- `data/processed/community-signals.json`
- `data/processed/issue-pr-linkage.json`
- `data/processed/analysis-results.json`
- `findings/summary.md`

## Method Notes

- `community` means a non-bot issue author without merge rights in `github/gh-aw`.
- Maintainers are identified only by merged PRs, not by PR volume or labels.
- Category buckets (`doc`, `bug`, `enhancement`, `uncategorized`) are heuristic and should be treated as descriptive.
- PR linkage only counts explicit closing phrases like `fixes #123`; plain `#123` references are excluded.

## Structure

```text
data/
  raw/              # Raw JSON from GitHub API
  processed/        # Cleaned, classified datasets
scripts/            # Data collection and analysis scripts
findings/           # Generated markdown summary
```

## License

MIT

## Context

This analysis grew out of contributing to gh-aw as a community member. Over the course of building [prd-to-prod](https://github.com/samuelkahessay/prd-to-prod), an autonomous software pipeline on top of gh-aw, I filed issues against the platform and used those experiences as a starting point for a broader repository-level pass.
