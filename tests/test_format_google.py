import unittest

from p2p_rates.bybit import Ad, Quote
from p2p_rates.format import fmt_pct, render

GOOGLE = 81.48


def ad(price, nick="Trader"):
    return Ad(nick=nick, price=price, min_rub=1000.0, max_rub=900000.0, qty_usdt=9999.0,
              payments=("14",), online=True, rate=100.0, orders30=300, national_limit=False)


def quote(*prices):
    return Quote(ads=[ad(p, f"m{i}") for i, p in enumerate(prices)], reference=prices[len(prices) // 2])


class PctTests(unittest.TestCase):
    def test_signs(self):
        self.assertEqual(fmt_pct(2.74), "+2,7 %")
        self.assertEqual(fmt_pct(-1.34), "-1,3 %")
        self.assertEqual(fmt_pct(0.0), "0,0 %")
        self.assertEqual(fmt_pct(0.04), "0,0 %")


class GoogleLineTests(unittest.TestCase):
    def test_header_shows_google_rate(self):
        text = render(50000, "buy", quote(83.49, 83.7, 83.9, 84.0), None, False, google=GOOGLE)
        self.assertIn("Google", text)
        self.assertIn("1 USD = <b>81,48 ₽</b>", text)

    def test_premium_per_ad(self):
        text = render(50000, "buy", quote(83.70, 83.9, 84.0), None, False, google=GOOGLE)
        # 83.70 / 81.48 - 1 = +2.72 %
        self.assertIn("+2,7 %", text)

    def test_no_google_no_premium(self):
        text = render(50000, "buy", quote(83.70, 83.9, 84.0), None, False, google=None)
        self.assertNotIn("Google", text)
        self.assertNotIn("%</b>", text)

    def test_negative_difference_uses_hyphen(self):
        text = render(50000, "sell", None, quote(80.0, 79.5, 79.0), False, google=GOOGLE)
        self.assertIn("-1,8 %", text)
        self.assertNotIn("−", text)
        self.assertNotIn("—", text)


class PickTests(unittest.TestCase):
    def test_pick_is_third_for_three_or_more(self):
        text = render(50000, "buy", quote(83.49, 83.70, 83.90, 84.0), None, False, google=GOOGLE)
        self.assertIn("Разумный выбор", text)
        line = [l for l in text.splitlines() if "Разумный выбор" in l][0]
        self.assertIn("83,90", line)

    def test_no_pick_for_short_list(self):
        text = render(50000, "buy", quote(83.49, 83.70), None, False, google=GOOGLE)
        self.assertNotIn("Разумный выбор", text)

    def test_pick_for_sell_is_third_highest(self):
        text = render(50000, "sell", None, quote(98.0, 97.0, 96.0, 95.0), False, google=GOOGLE)
        line = [l for l in text.splitlines() if "Разумный выбор" in l][0]
        self.assertIn("96,00", line)

    def test_pick_shown_even_without_google(self):
        text = render(50000, "buy", quote(83.49, 83.70, 83.90), None, False, google=None)
        self.assertIn("Разумный выбор", text)


if __name__ == "__main__":
    unittest.main()
