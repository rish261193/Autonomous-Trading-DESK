"""CLI for offline strategy research. Example: python -m trading_desk research prices.csv"""
import argparse
import json
from .research import load_csv, walk_forward, Costs

def main():
    parser = argparse.ArgumentParser(description="Offline paper strategy research; no broker connection")
    sub = parser.add_subparsers(dest="command", required=True)
    research = sub.add_parser("research")
    research.add_argument("csv", help="CSV containing timezone-aware timestamp and close")
    research.add_argument("--fee-bps", type=float, default=10.0)
    research.add_argument("--slippage-bps", type=float, default=5.0)
    args = parser.parse_args()
    if args.command == "research":
        bars = load_csv(args.csv)
        report = walk_forward(bars, range(2, 11), range(12, 41), costs=Costs(args.fee_bps, args.slippage_bps))
        print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
