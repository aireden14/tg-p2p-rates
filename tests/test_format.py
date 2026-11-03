import unittest

from p2p_rates.bybit import Ad, Quote
from p2p_rates.format import fmt_int, fmt_price, fmt_usdt, parse_amount, render


def ad(**kw):
    base = dict(
        nick="Trader", price=82.35, min_rub=1000.0, max_rub=191015.0, qty_usdt=2300.0,
        payments=("14",), online=True, rate=100.0, orders30=433, national_limit=False,
    )
    base.update(kw)
    return Ad(**base)


class NumberFormatTests(unittest.TestCase):
    def test_fmt_int(self):
        self.assertEqual(fmt_int(50000), "50 000")
        self.assertEqual(fmt_int(1234567), "1 234 567")
        self.assertEqual(fmt_int(500), "500")

    def test_fmt_price(self):
        self.assertEqual(fmt_price(82.35), "82,35")
        self.assertEqual(fmt_price(93.5), "93,50")

    def test_fmt_usdt(self):
        self.assertEqual(fmt_usdt(607.1428), "607,14")
        self.assertEqual(fmt_usdt(1234.5), "1 234,50")


class ParseAmountTests(unittest.TestCase):
    def test_variants(self):
        cases = {
            "50000": 50000, "50 000": 50000, "50k": 50000, "50к": 50000, "50 К": 50000,
            "100000 руб": 100000, "100000₽": 100000, "1.5м": 1500000, "1,5 млн": 1500000,
            "2 млн": 2000000, "/rate 70000": 70000, "  15000  ": 15000,
        }
        for text, want in cases.items():
            with self.subTest(text):
                self.assertEqual(parse_amount(text), want)

    def test_rejects(self):
        for text in ["", "привет", "abc 12", "0", "-5000", "100", "999999999"]:
            with self.subTest(text):
                self.assertIsNone(parse_amount(text))


class RenderTests(unittest.TestCase):
    def quotes(self):
        buy = Quote(ads=[ad(nick="prepodBTC", price=82.35), ad(nick="KACHOK777", price=83.79, orders30=663)], reference=84.1)
        sell = Quote(ads=[ad(nick="Irina77", price=93.5, orders30=564)], reference=93.5)
        return buy, sell

    def test_both_contains_prices_and_conversion(self):
        buy, sell = self.quotes()
        text = render(50000, "both", buy, sell, bank_only=False)
        self.assertIn("50 000", text)
        self.assertIn("82,35", text)
        self.assertIn("93,50", text)
        self.assertIn("607,16", text)  # 50000 / 82.35 = 607.1645
        self.assertIn("prepodBTC", text)
        self.assertIn("Bybit", text)

    def test_single_direction_hides_other(self):
        buy, sell = self.quotes()
        text = render(50000, "buy", buy, None, bank_only=False)
        self.assertIn("prepodBTC", text)
        self.assertNotIn("Irina77", text)

    def test_nick_is_html_escaped(self):
        buy = Quote(ads=[ad(nick="<b>evil&</b>")], reference=82.35)
        text = render(50000, "buy", buy, None, bank_only=False)
        self.assertNotIn("<b>evil", text)
        self.assertIn("&lt;b&gt;evil&amp;&lt;/b&gt;", text)

    def test_empty_quote(self):
        text = render(50000, "buy", Quote(ads=[], reference=None), None, bank_only=False)
        self.assertIn("нет подходящих объявлений", text)

    def test_warning_when_sell_above_buy(self):
        buy, sell = self.quotes()
        text = render(50000, "both", buy, sell, bank_only=False)
        self.assertIn("продажи выше", text)

    def test_no_warning_when_normal(self):
        buy = Quote(ads=[ad(price=95.0)], reference=95.0)
        sell = Quote(ads=[ad(price=93.0)], reference=93.0)
        text = render(50000, "both", buy, sell, bank_only=False)
        self.assertNotIn("продажи выше", text)

    def test_bank_only_label(self):
        buy, _ = self.quotes()
        self.assertIn("только банковский перевод", render(50000, "buy", buy, None, bank_only=True))


if __name__ == "__main__":
    unittest.main()
