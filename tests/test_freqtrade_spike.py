"""Offline regression tests for Freqtrade compatibility preflight."""
import copy
import unittest

from trading_desk.freqtrade_spike import (
    UnsafeFreqtradeConfiguration, validate_freqtrade_paper_config,
)


def safe_config():
    return {
        "dry_run": True, "trading_mode": "spot", "stake_currency": "USD",
        "dry_run_wallet": 500, "max_open_trades": 2,
        "exchange": {"name": "kraken", "pair_whitelist": ["BTC/USD", "ETH/USD"]},
        "pairlists": [{"method": "StaticPairList"}],
        "api_server": {"enabled": False},
        "db_url": "sqlite:///freqtrade_spike.dryrun.sqlite",
    }


class FreqtradePreflightTests(unittest.TestCase):
    def test_safe_paper_configuration(self):
        self.assertIsNone(validate_freqtrade_paper_config(safe_config()))

    def test_rejects_unsafe_variations(self):
        variations = [
            ("dry_run", False), ("trading_mode", "futures"),
            ("stake_currency", "USDT"), ("dry_run_wallet", 1000),
            ("dry_run_wallet", float("nan")), ("margin_mode", "isolated"),
            ("max_open_trades", 3), ("force_entry_enable", True),
            ("position_adjustment_enable", True),
            ("api_server", {"enabled": True}), ("db_url", "postgresql://localhost/x"),
            ("pairlists", [{"method": "VolumePairList"}]),
        ]
        for key, value in variations:
            with self.subTest(key=key, value=str(value)):
                config = safe_config()
                config[key] = value
                with self.assertRaises(UnsafeFreqtradeConfiguration):
                    validate_freqtrade_paper_config(config)

    def test_rejects_credentials_and_extra_pairs(self):
        for key in ("key", "secret", "password", "api_key", "api_secret"):
            config = safe_config()
            config["exchange"][key] = "not-allowed"
            with self.subTest(key=key), self.assertRaises(UnsafeFreqtradeConfiguration):
                validate_freqtrade_paper_config(config)
        config = safe_config()
        config["exchange"]["pair_whitelist"].append("SOL/USD")
        with self.assertRaises(UnsafeFreqtradeConfiguration):
            validate_freqtrade_paper_config(config)

    def test_rejects_missing_and_nonmapping(self):
        with self.assertRaises(UnsafeFreqtradeConfiguration):
            validate_freqtrade_paper_config(None)
        config = safe_config()
        del config["dry_run"]
        with self.assertRaises(UnsafeFreqtradeConfiguration):
            validate_freqtrade_paper_config(config)


if __name__ == "__main__":
    unittest.main()
