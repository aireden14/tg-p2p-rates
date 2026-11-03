import unittest
from datetime import datetime

from p2p_rates.format import fmt_rub, fmt_signed, render_estimate, render_unavailable
from p2p_rates.rates import estimate

NOW = datetime(2026, 11, 3, 19, 55, 1)


class NumberTests(unittest.TestCase):
    def test_fmt_signed(self):
        self.assertEqual(fmt_signed(2.5), "+2,50")
        self.assertEqual(fmt_signed(-1.0), "-1,00")
        self.assertEqual(fmt_signed(0), "+0,00")

    def test_fmt_rub_large_is_integer(self):
        self.assertEqual(fmt_rub(4_200_000), "4 200 000")

    def test_fmt_rub_small_keeps_kopecks(self):
        self.assertEqual(fmt_rub(253.11), "253,11")


class RenderEstimateTests(unittest.TestCase):
    def test_both_directions_for_one_amount(self):
        text = render_estimate(50_000, estimate(50_000, 81.5, 2.5, 2.5), 81.5, 2.5, 2.5, now=NOW)
        self.assertIn("50 000 ₽ → USDT", text)
        self.assertIn("595,24 USDT", text)
        self.assertIn("50 000 USDT → ₽", text)
        self.assertIn("4 200 000 ₽", text)

    def test_formula_is_hidden_and_source_label_shown(self):
        text = render_estimate(50_000, estimate(50_000, 81.5, 2.5, 2.5), 81.5, 2.5, 2.5, now=NOW)
        self.assertIn("84,00", text)
        self.assertIn("Bybit P2P", text)
        self.assertNotIn("Google", text)
        self.assertNotIn("+2,50", text)
        self.assertIn("Обновлено 19:55:01", text)

    def test_different_markups_show_both_prices(self):
        text = render_estimate(10_000, estimate(10_000, 81.5, 3.0, 1.0), 81.5, 3.0, 1.0, now=NOW)
        self.assertIn("84,50", text)
        self.assertIn("82,50", text)
        self.assertNotIn("+3,00", text)
        self.assertNotIn("Google", text)

    def test_no_long_dash_and_no_live_ads_claim(self):
        text = render_estimate(50_000, estimate(50_000, 81.5, 2.5, 2.5), 81.5, 2.5, 2.5, now=NOW)
        self.assertNotIn("—", text)
        self.assertIn("оценка", text.lower())

    def test_unavailable_message(self):
        text = render_unavailable()
        self.assertIn("Google", text)
        self.assertIn("недоступен", text)
        self.assertNotIn("≈", text)


if __name__ == "__main__":
    unittest.main()
