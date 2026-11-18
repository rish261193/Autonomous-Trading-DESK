# Integrated offline research pipeline

The `research_pipeline` function connects existing components:

1. Validates time-ordered historical price observations.
2. Generates rolling train/holdout windows with an optional embargo.
3. Evaluates parameter combinations on **training data only**.
4. Selects the strongest training candidate and evaluates it on holdout observations.
5. Records estimated transaction costs, strategy parameters and results.
6. Creates a SHA-256 fingerprint of input price data and optionally appends an audit record.
7. Can save the complete report to JSON.

## Example Python usage

```python
from trading_desk.research import load_csv, Costs
from trading_desk.pipeline import research_pipeline, save_pipeline_report

bars = load_csv("my_historical_btc_data.csv")
report = research_pipeline(
    bars, fast_values=[3, 5, 8], slow_values=[15, 20, 30],
    train_size=300, test_size=100, gap=1, costs=Costs(10, 5),
    audit_path="logs/research.jsonl",
)
save_pipeline_report(report, "reports/research.json")
```

The example assumes you have a suitably large, timezone-aware CSV file. No dataset is bundled and no external API is called.

## Limitations

This is an **offline research prototype**, not a live or paper-trading execution engine. The underlying SMA backtester has simplified close-price fills, no stop-loss enforcement, and no mandatory midnight liquidation; positions may cross UTC dates. Its research outcomes cannot be used as evidence of sustainable profitability. Each rolling window is evaluated independently rather than as a stitched equity curve. A two-point equity return is included as a summary, not as a valid volatility or Sharpe estimate.

Before considering paper execution, implement event-driven realistic fills, 24/7 position monitoring and UTC daily loss accounting, robust position sizing, risk gateway integration, and independent evaluation on real market data.
