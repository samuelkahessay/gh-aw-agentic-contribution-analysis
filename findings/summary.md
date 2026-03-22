# Analysis Summary

## Sample

- Total issues: 7684
- Bot-authored issues: 6648 (86.5%)
- Maintainer-authored issues: 601 (7.8%)
- Community issues: 435 (5.7%) from 158 contributors
- Community label coverage on community issues: 59.5%

## Strongest descriptive patterns

- Enhancements have the slowest median closure time: 2.974 days.
- Within labeled bugs, error output shifts median closure time from 2.325 to 0.47 days.
- Body length is weakly informative: medians range from 0.087 to 0.401 days across buckets.
- Filtered timeline associations link 192 of 379 closed community issues (50.7%) to at least one plausible pre-close PR.
- In that PR-side sample, 88.1% of merged linked PRs are bot-authored.

## Limitations

- Role classification is conservative: "community" means any non-bot issue author without merge rights in gh-aw.
- Category buckets are heuristic label/title groupings used for descriptive analysis, not causal inference.
- PR linkage uses GitHub Timeline API associations filtered to PRs created before issue closure; this improves recall but still yields plausible rather than definitive fix links.
- Issue-side findings are stronger than the PR-side authorship slice, which depends on moderate-confidence linkage heuristics.
