"""Independent quant study using the repository's own research code on real daily data.
Run: python -I quant_study.py <repo_src> <btc_csv> <eth_csv>"""
import sys, json, random, math, statistics
sys.path.insert(0, sys.argv[1])
from trading_desk.research import load_csv, walk_forward, Costs, backtest, grid_search
from trading_desk.pipeline import research_pipeline
from trading_desk.simulator import simulate, screen
from trading_desk.signals import SignalSpec
from datetime import datetime, timezone

def since(bars, y):
    t = datetime(y,1,1,tzinfo=timezone.utc); return [b for b in bars if b.timestamp >= t]

def bh(bars, charge_bps):
    c = charge_bps/1e4
    return 100*((bars[-1].close*(1-c))/(bars[0].close*(1+c)) - 1)

out = {}
for name, path in (("BTC", sys.argv[2]), ("ETH", sys.argv[3])):
    bars = since(load_csv(path), 2018)
    r = {"bars": len(bars), "start": bars[0].timestamp.date().isoformat(), "end": bars[-1].timestamp.date().isoformat()}
    for label, costs in (("15bps", Costs(10,5)), ("60bps", Costs(50,10)), ("100bps", Costs(80,20))):
        wf = walk_forward(bars, range(2,11), range(12,41), costs=costs)
        cut = wf["train_bars"]; hold = bars[cut:]
        r[f"walk_forward_{label}"] = {
            "selected": {k: wf["selected_on_training_only"][k] for k in ("fast","slow","net_return_pct","trades")},
            "holdout_net_return_pct": round(wf["untouched_holdout"]["net_return_pct"],2),
            "holdout_max_dd_pct": round(wf["untouched_holdout"]["max_drawdown_pct"],2),
            "holdout_trades": wf["untouched_holdout"]["trades"],
            "buy_and_hold_holdout_pct": round(bh(hold, costs.fee_bps+costs.slippage_bps),2),
            "holdout_period": [hold[0].timestamp.date().isoformat(), hold[-1].timestamp.date().isoformat()],
        }
    rp = research_pipeline(bars, list(range(2,11)), list(range(12,41)), train_size=730, test_size=180, gap=1, costs=Costs(10,5))
    wins = []
    for w in rp["windows"]:
        s = w["split"]; hold = bars[s["test_start"]:s["test_end"]]
        wins.append({"window": w["window"], "sel": w["selected_on_train"], "strategy_pct": round(w["holdout"]["net_return_pct"],2),
                     "buy_hold_pct": round(bh(hold,15),2), "trades": w["holdout"]["trades"]})
    beat = sum(1 for w in wins if w["strategy_pct"] > w["buy_hold_pct"])
    pos = sum(1 for w in wins if w["strategy_pct"] > 0)
    diffs = [w["strategy_pct"]-w["buy_hold_pct"] for w in wins]
    r["rolling_pipeline_15bps"] = {"windows": wins, "beat_buy_hold": f"{beat}/{len(wins)}", "positive": f"{pos}/{len(wins)}",
        "mean_excess_vs_bh_pct": round(statistics.mean(diffs),2), "stdev_excess_pct": round(statistics.stdev(diffs),2),
        "t_stat_excess": round(statistics.mean(diffs)/(statistics.stdev(diffs)/math.sqrt(len(diffs))),2)}
    # Multiple-testing null: best in-sample of N random long/flat signals vs best real family config.
    specs = [SignalSpec(f, lb, th) for f in ("momentum","mean_reversion","breakout") for lb in (2,3,5,8,10,15,20,30,50,100) for th in (0,50,100,200)]
    cut = int(len(bars)*0.7); train, test = bars[:cut], bars[cut-101:]
    ranked = screen(train, specs, Costs(10,5))
    best = ranked[0]
    best_test = simulate(test, SignalSpec(best.family, best.lookback, best.threshold_bps), Costs(10,5))
    r["family_screen_120_configs"] = {"best_in_sample": {"family": best.family, "lookback": best.lookback, "threshold_bps": best.threshold_bps, "net_return_pct": round(best.net_return_pct,1), "trades": best.trades},
        "same_config_holdout_net_pct": round(best_test.net_return_pct,1),
        "holdout_buy_hold_pct": round(bh(bars[cut:],15),1),
        "median_in_sample_config_pct": round(statistics.median(x.net_return_pct for x in ranked),1),
        "share_of_configs_beating_in_sample_buy_hold": f"{sum(1 for x in ranked if x.net_return_pct > bh(train[101:],15))}/{len(ranked)}"}
    # Random-signal null: 120 random long/flat strategies with p(long)=0.5, daily switching prob 0.1
    rng = random.Random(7); closes=[b.close for b in train]; best_rand=-1e9; rand=[]
    for k in range(120):
        state=False; cash=500.0; units=0.0; ch=15/1e4
        for i in range(1,len(closes)):
            if rng.random()<0.1: state = not state
            p=closes[i]
            if state and not units: units=cash/(p*(1+ch)); cash=0
            elif not state and units: cash=units*p*(1-ch); units=0
        if units: cash=units*closes[-1]*(1-ch)
        rand.append(100*(cash/500-1))
    r["random_signal_null_in_sample"] = {"n": 120, "best_pct": round(max(rand),1), "median_pct": round(statistics.median(rand),1)}
    out[name]=r
print(json.dumps(out, indent=1))
