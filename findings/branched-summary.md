# Branched Analysis Summary

## Sample

- Community issues: 435
- Closed: 379
  - bug: 55 total, 42 closed
  - enhancement: 25 total, 19 closed
  - uncategorized: 336 total, 302 closed
  - doc: 19 total, 16 closed

## Uncategorized clusters

- **failure_shaped**: 194 issues (169 closed), median 0.152d, 85.2% same-day
- **change_shaped**: 61 issues (56 closed), median 0.222d, 76.8% same-day
- **minimal**: 81 issues (77 closed), median 0.105d, 84.4% same-day

## Enhancement shape

- **fast** (<1d / 1-5d / >5d): n=8, median=0.367d
- **mid** (<1d / 1-5d / >5d): n=3, median=2.974d
- **slow** (<1d / 1-5d / >5d): n=8, median=9.978d
- Bimodality usable: True (gap=6.005d)

## Lead candidates

- **signal_reversal**: hasErrorOutput flips sign across lanes with magnitude >= 20%
- **signal_reversal**: hasRunLink flips sign across lanes with magnitude >= 20%
- **signal_reversal**: hasLineNumber flips sign across lanes with magnitude >= 20%
- **signal_reversal**: hasProposedCode flips sign across lanes with magnitude >= 20%
- **signal_reversal**: hasSuggestedFix flips sign across lanes with magnitude >= 20%
- **enhancement_bimodality**: Enhancement closure is bimodal: gap of 6.005d between fast and slow clusters
- **label_selection_effect**: bug_vs_failure_shaped: >=3x ratio in 5 matched cells
- **label_selection_effect**: enhancement_vs_change_shaped: >=3x ratio in 5 matched cells
- **contributor_variance**: 1 signals differ by >=10pp between same contributors' fast vs slow issues
