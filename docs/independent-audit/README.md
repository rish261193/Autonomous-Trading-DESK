# Independent full-system audit (2026-11-18)

Audited commit: `53e0870` (`main`). Fixes and tests are on `audit/independent-full-system-review`.

| File | Contents |
|---|---|
| [01_EXECUTIVE_VERDICT.md](01_EXECUTIVE_VERDICT.md) | Verdict, scorecard, answers to the 15 questions |
| [02_ARCHITECTURE_REVIEW.md](02_ARCHITECTURE_REVIEW.md) | History, implementation inventory, current vs recommended architecture (Mermaid) |
| [03_CODE_AND_SECURITY_FINDINGS.md](03_CODE_AND_SECURITY_FINDINGS.md) | Findings F-01…F-17 with reproduction, status and interface changes |
| [04_QUANTITATIVE_REVIEW.md](04_QUANTITATIVE_REVIEW.md) | Real-data test of the repo's research code; validation framework |
| [05_TEST_RESULTS.md](05_TEST_RESULTS.md) | Exact commands, baseline vs final results, new tests, mutation check |
| [06_RISK_AND_ACCOUNTING_REVIEW.md](06_RISK_AND_ACCOUNTING_REVIEW.md) | Control-by-control verification and adverse scenarios |
| [07_AGENT_ARCHITECTURE_REVIEW.md](07_AGENT_ARCHITECTURE_REVIEW.md) | All 11 roles evaluated; leanest viable design |
| [08_COST_AND_COMMERCIALIZATION.md](08_COST_AND_COMMERCIALIZATION.md) | Sourced prices, cost scenarios, break-even, commercialization |
| [09_GPT6_ENGINEERING_SCORECARD.md](09_GPT6_ENGINEERING_SCORECARD.md) | Right / wrong / missed / change / stop / next |
| [10_RECOMMENDED_ROADMAP.md](10_RECOMMENDED_ROADMAP.md) | Gated phases with acceptance criteria |
| [11_INTEGRATION_CONTRACT.md](11_INTEGRATION_CONTRACT.md) | Proposed service API between ledger and agents |
| [evidence/](evidence/) | Probe and quant scripts, raw outputs, test logs, mutation results |

Reproduce the probes from the repo root: `python -I docs/independent-audit/evidence/probe.py src`.
Reproduce the quant study: download `csv/btc.csv` and `csv/eth.csv` from GitHub `coinmetrics/data`, convert them with `evidence/prep.py`, then run `evidence/quant_study.py src btc_daily.csv eth_daily.csv`.
