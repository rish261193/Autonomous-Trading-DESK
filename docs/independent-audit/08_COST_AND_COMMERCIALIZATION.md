# 08 — Operating economics and commercialization

## Price sources (retrieved 2026-11-18)

| Item | Figure used | Source | Verification |
|---|---|---|---|
| Alpaca crypto fees, tier 1 (<$100k 30-day vol) | 0.15% maker / 0.25% taker | docs.alpaca.markets/docs/crypto-fees | Vendor documentation |
| Kraken Pro spot, tier 1 | 0.40% maker / 0.80% taker | kraken.com/help/fees-and-pair-info, kraken.com/ca/pro/fees | Vendor page. Third-party pages still quote older 0.25/0.40, so check the live schedule. |
| Coinbase Advanced, lowest tier | 0.60% maker / 1.20% taker per Bankrate; other sources differ | bankrate.com Coinbase review | **Unverified.** Coinbase shows the full schedule only when logged in. |
| OpenAI API (GPT-6 Luna / Sol / Astra) | $0.10/$0.50, $2/$10, $10/$50 per 1M in/out tokens | benchlm.ai, costbench.com (state they were checked against OpenAI's pricing page in Oct 2026) | **Third-party; not verified at source.** |
| WhatsApp Business Platform | Per delivered message, by category and country; service messages charged from 2026-10-01 | developers.facebook.com WhatsApp pricing; courier.com explainer | Model verified; **per-message rate for Canada not verified** |
| Small VPS (Hetzner CX-class) | ≈ €4–€8/month; Hetzner raised prices in 2026 | third-party trackers | **Unverified range**; check at purchase |
| Market data | $0 for exchange public REST/WebSocket feeds (Alpaca provides free limited crypto data) | Alpaca docs | Limited tier only |

Nothing else here is a verified price. Everything else is an assumption and is labelled as one.

## Monthly cost scenarios

| Scenario | Components | Estimate | Notes |
|---|---|---|---|
| 1. Local development | Laptop, stdlib Python, free public data, occasional LLM use in ChatGPT/IDE | **$0 incremental** | Matches today's repo |
| 2. Minimal cloud paper deployment (deterministic only) | 1 small VPS, SQLite, cron, e-mail alerts, exchange public data | **≈ $5–$10** (assumption) | No LLM in the loop |
| 3. Unattended paper with the 11-agent design | VPS + backups + uptime monitor + LLM calls + WhatsApp | **$30 to $700+** (see LLM table) | Dominated by model choice and call frequency |
| 3b. Unattended paper, lean design (`07`) | VPS + weekly research LLM batch + daily summary | **≈ $8–$20** | Fits $30 with margin |
| 4. Early subscription product | Multi-tenant app, managed DB, auth, payments, per-user exchange keys (encrypted), monitoring, support, legal review, insurance | **Hundreds to thousands per month** before legal fees (assumption) | Legal and compliance costs dominate, not compute |

### LLM cost sensitivity (11 agents, 4k-in/1k-out tokens per call, 30 days)

| Calls/day | Luna | Sol | Astra |
|---|---|---|---|
| 44 (each agent 4×/day) | $1.19 | $23.76 | $118.80 |
| 264 (each agent hourly) | $7.13 | $142.56 | $712.80 |
| 1,056 (each agent every 15 min) | $28.51 | $570.24 | $2,851.20 |

The 11-agent design only fits a $30 budget with the cheapest model at low frequency.

## Returns required to cover costs on $500

| Monthly opex | Required net monthly return | Compounded annual |
|---|---|---|
| $5 | 1.0% | 13% |
| $10 | 2.0% | 27% |
| $30 | **6.0%** | **101%** |
| $60 | 12.0% | 290% |

With $5 risk per trade, a strategy that clears +0.2R per trade *after* costs (strong for a retail systematic crypto strategy, and unproven here) earns $1/trade. That needs **30 qualifying trades a month just to pay $30**, before any profit. Round-trip tier-1 fees alone cost 0.10R–1.60R per trade depending on venue and stop distance (`06`).

**Conclusion:** at $500, operating costs, not trading skill, set the result. Run with the paper ledger as a *research instrument* costing at most $10/month, and judge strategies in R per trade net of trading costs. Opex is a fixed cost to compare against capital you might deploy later. Don't present it as something $500 should pay for.

## Commercialization

**Don't assume a working personal strategy becomes a subscription business.** Several conditions have to hold separately:

| Question | Assessment |
|---|---|
| Target customer | Unclear. "Autonomous AI crypto desk" competes with exchange-native bots, copy-trading platforms and open-source tools such as Freqtrade (listed in `TOOLS.md`). |
| Value proposition | Today the differentiator is "AI agents". Buyers will pay for **verified net performance** and **trustworthy risk controls**, and neither exists yet. |
| Differentiation that could be real | The tamper-evident, replayable ledger plus independent risk gateway is credible infrastructure. "Transparent, verifiable paper/live track record with hash-anchored history" is a defensible angle. "11 AI agents" isn't. |
| Performance transparency | Required: per-strategy net results after fees, including failed strategies, with an auditable history. The ledger work here is the right foundation. |
| Data licensing | Redistributing exchange or aggregator data to subscribers usually needs a commercial licence. Coin Metrics community data (used in `04`) has its own terms; read them before any commercial use. |
| Exchange integrations | Per-customer API keys mean custody-adjacent security obligations (key encryption, withdrawal-disabled keys, incident response). |
| Regulation | **I'm not a lawyer, and this isn't legal advice.** In Ontario, the OSC states that any business advising on or trading in securities or derivatives must be registered unless an exemption applies. Canadian regulators have treated many crypto-trading arrangements as securities or derivatives activity. Selling signals, automated execution or managed strategies may therefore require registration (dealer or adviser categories under NI 31-103) or a specific exemption. Similar questions arise in the US (investment adviser and CFTC rules) and the EU (MiCA). Get advice from securities counsel in each target jurisdiction **before** marketing anything. |
| Performance advertising | Backtested or hypothetical performance is heavily restricted in marketing by many regulators. Don't publish backtest returns as performance claims. |
| Support and reliability | 24/7 crypto means 24/7 incidents. A solo operator can't credibly offer autonomous execution SLAs. |
| Subscription economics | Unknown demand. Validate with a waitlist or interviews *after* a verified paper track record, not before. |

### What must be proven before commercialization

1. A strategy passing the validation framework in `04` on untouched data.
2. A paper track record meeting the pre-computed trade count, with net expectancy CI > 0 after realistic costs.
3. A small live track record (owner capital, separately authorized) that matches paper within tolerance.
4. Unattended operation for ≥ 30 days with zero accounting discrepancies and documented incident handling.
5. A legal opinion on the product structure (signals vs. software vs. managed execution) for the target jurisdictions.
