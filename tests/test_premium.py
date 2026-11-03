import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from p2p_rates.bot import Bot, Store
from p2p_rates.format import render_estimate
from p2p_rates.rates import DEFAULT_PREMIUM_PCT, estimate, load_premium

NOW = datetime(2026, 11, 4, 9, 0, 0)


class EstimatePremiumTests(unittest.TestCase):
    def test_premium_scales_both_prices(self):
        e = estimate(50_000, 81.5, 2.5, 2.5, premium_pct=1.5)
        self.assertAlmostEqual(e.buy_price, 85.26)    # (81.5 + 2.5) * 1.015
        self.assertAlmostEqual(e.sell_price, 85.26)
        self.assertAlmostEqual(e.usdt_for_rub, 50_000 / 85.26)
        self.assertAlmostEqual(e.rub_for_usdt, 50_000 * 85.26)

    def test_zero_premium_is_old_behavior(self):
        e = estimate(50_000, 81.5, 2.5, 2.5)
        self.assertAlmostEqual(e.buy_price, 84.0)
        self.assertAlmostEqual(estimate(50_000, 81.5, 2.5, 2.5, premium_pct=0).buy_price, 84.0)

    def test_premium_applies_after_markup_with_different_markups(self):
        e = estimate(10_000, 81.5, 3.0, 1.0, premium_pct=2.0)
        self.assertAlmostEqual(e.buy_price, 84.5 * 1.02)
        self.assertAlmostEqual(e.sell_price, 82.5 * 1.02)


class LoadPremiumTests(unittest.TestCase):
    def test_default_is_one_and_a_half_percent(self):
        self.assertEqual(DEFAULT_PREMIUM_PCT, 1.5)
        self.assertEqual(load_premium({}), 1.5)

    def test_from_env(self):
        self.assertEqual(load_premium({"P2P_PREMIUM_PCT": "2"}), 2.0)
        self.assertEqual(load_premium({"P2P_PREMIUM_PCT": "2,5"}), 2.5)
        self.assertEqual(load_premium({"P2P_PREMIUM_PCT": "0"}), 0.0)
        self.assertEqual(load_premium({"P2P_PREMIUM_PCT": "-1"}), -1.0)

    def test_garbage_and_absurd_fall_back(self):
        self.assertEqual(load_premium({"P2P_PREMIUM_PCT": "abc"}), 1.5)
        self.assertEqual(load_premium({"P2P_PREMIUM_PCT": ""}), 1.5)
        self.assertEqual(load_premium({"P2P_PREMIUM_PCT": "50"}), 1.5)


class RenderPremiumTests(unittest.TestCase):
    def test_percent_is_applied_but_not_shown(self):
        est = estimate(50_000, 81.5, 2.5, 2.5, premium_pct=1.5)
        text = render_estimate(50_000, est, 81.5, 2.5, 2.5, now=NOW, premium_pct=1.5)
        self.assertIn("85,26", text)
        self.assertNotIn("Google", text)
        self.assertNotIn("%", text)
        self.assertIn("586,44 USDT", text)
        self.assertIn("4 263 000 ₽", text)

    def test_no_percent_when_zero(self):
        est = estimate(50_000, 81.5, 2.5, 2.5)
        text = render_estimate(50_000, est, 81.5, 2.5, 2.5, now=NOW)
        self.assertNotIn("%", text)

    def test_different_markups_with_percent(self):
        est = estimate(10_000, 81.5, 3.0, 1.0, premium_pct=1.5)
        text = render_estimate(10_000, est, 81.5, 3.0, 1.0, now=NOW, premium_pct=1.5)
        self.assertNotIn("%", text)
        self.assertIn("85,77", text)  # 84.5 * 1.015 = 85.7675
        self.assertIn("83,74", text)  # 82.5 * 1.015 = 83.7375


class FakeGoogle:
    def usd_rub(self):
        return 81.5


class FakeApi:
    def __init__(self):
        self.calls = []

    def call(self, method, **params):
        self.calls.append((method, params))
        return {"message_id": 1}


class BotPremiumTests(unittest.TestCase):
    def test_bot_applies_premium(self):
        api = FakeApi()
        store = Store(Path(tempfile.mkdtemp()) / "state.json")
        bot = Bot(api, FakeGoogle(), store, buy_markup=2.5, sell_markup=2.5, premium_pct=1.5)
        bot.handle_update({"update_id": 1, "message": {"message_id": 1, "chat": {"id": 7}, "text": "50000"}})
        text = [p for m, p in api.calls if m == "sendMessage"][-1]["text"]
        self.assertIn("586,44 USDT", text)
        self.assertIn("4 263 000 ₽", text)

    def test_bot_default_premium_is_zero_for_backward_compat(self):
        api = FakeApi()
        store = Store(Path(tempfile.mkdtemp()) / "state.json")
        bot = Bot(api, FakeGoogle(), store)
        bot.handle_update({"update_id": 1, "message": {"message_id": 1, "chat": {"id": 7}, "text": "50000"}})
        text = [p for m, p in api.calls if m == "sendMessage"][-1]["text"]
        self.assertIn("595,24 USDT", text)


if __name__ == "__main__":
    unittest.main()
