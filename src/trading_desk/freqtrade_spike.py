"""Fail-closed preflight for an isolated Freqtrade dry-run experiment.

This is a configuration gate, NOT a trading authorization boundary.
No Freqtrade import, process launch, broker access, or live trading.
"""
from __future__ import annotations

from math import isfinite


class UnsafeFreqtradeConfiguration(ValueError):
    pass


def validate_freqtrade_paper_config(config: dict) -> None:
    """Reject configuration that violates our initial paper-only scope."""
    if not isinstance(config, dict):
        raise UnsafeFreqtradeConfiguration("Configuration must be a mapping")
    if config.get("dry_run") is not True:
        raise UnsafeFreqtradeConfiguration("Dry-run must be explicitly enabled")
    if config.get("trading_mode") != "spot":
        raise UnsafeFreqtradeConfiguration("Only spot trading is allowed")
    if config.get("stake_currency") != "USD":
        raise UnsafeFreqtradeConfiguration("Paper wallet must use USD")
    wallet = config.get("dry_run_wallet")
    if type(wallet) not in (int, float) or not isfinite(wallet) or wallet != 500:
        raise UnsafeFreqtradeConfiguration("Paper wallet must be exactly 500 USD")
    if config.get("margin_mode") not in (None, ""):
        raise UnsafeFreqtradeConfiguration("Margin mode is forbidden")
    exchange = config.get("exchange")
    if not isinstance(exchange, dict) or exchange.get("name") != "kraken":
        raise UnsafeFreqtradeConfiguration("Kraken exchange metadata required")
    if any(exchange.get(k) for k in ("key", "secret", "password", "api_key", "api_secret")):
        raise UnsafeFreqtradeConfiguration("No exchange credentials in paper config")
    allowed = {"BTC/USD", "ETH/USD"}
    pairs = exchange.get("pair_whitelist")
    if not isinstance(pairs, list) or not pairs or set(pairs) != allowed or len(pairs) != 2:
        raise UnsafeFreqtradeConfiguration("Exactly BTC/USD and ETH/USD required")
    if config.get("pairlists") != [{"method": "StaticPairList"}]:
        raise UnsafeFreqtradeConfiguration("Dynamic pair selection forbidden")
    if config.get("position_adjustment_enable") is True:
        raise UnsafeFreqtradeConfiguration("Position adjustment forbidden")
    if config.get("max_open_trades") not in (1, 2):
        raise UnsafeFreqtradeConfiguration("At most two open trades")
    if config.get("api_server", {}).get("enabled", False) is not False:
        raise UnsafeFreqtradeConfiguration("API server must be disabled")
    if config.get("force_entry_enable", False) is not False:
        raise UnsafeFreqtradeConfiguration("Manual forced entries forbidden")
    if config.get("db_url") is None or not str(config["db_url"]).startswith("sqlite:///"):
        raise UnsafeFreqtradeConfiguration("Separate SQLite dry-run database required")
