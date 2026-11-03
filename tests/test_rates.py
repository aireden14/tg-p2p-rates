import unittest

from p2p_rates.rates import DEFAULT_MARKUP_RUB, estimate, load_markups


class EstimateTests(unittest.TestCase):
    def test_same_markup_both_directions(self):
        e = estimate(50_000, 81.5, 2.5, 2.5)
        self.assertAlmostEqual(e.buy_price, 84.0)
        self.assertAlmostEqual(e.sell_price, 84.0)
        self.assertAlmostEqual(e.usdt_for_rub, 50_000 / 84.0)
        self.assertAlmostEqual(e.rub_for_usdt, 50_000 * 84.0)

    def test_different_markups(self):
        e = estimate(10_000, 81.5, 3.0, 1.0)
        self.assertAlmostEqual(e.buy_price, 84.5)
        self.assertAlmostEqual(e.sell_price, 82.5)
        self.assertAlmostEqual(e.usdt_for_rub, 10_000 / 84.5)
        self.assertAlmostEqual(e.rub_for_usdt, 10_000 * 82.5)

    def test_negative_markup_allowed(self):
        e = estimate(1_000, 81.5, 2.5, -1.5)
        self.assertAlmostEqual(e.sell_price, 80.0)


class MarkupConfigTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(load_markups({}), (DEFAULT_MARKUP_RUB, DEFAULT_MARKUP_RUB))

    def test_from_env(self):
        self.assertEqual(load_markups({"P2P_BUY_MARKUP": "3", "P2P_SELL_MARKUP": "1.5"}), (3.0, 1.5))

    def test_comma_decimal(self):
        self.assertEqual(load_markups({"P2P_BUY_MARKUP": "2,75"})[0], 2.75)

    def test_garbage_falls_back(self):
        self.assertEqual(load_markups({"P2P_BUY_MARKUP": "abc", "P2P_SELL_MARKUP": ""}),
                         (DEFAULT_MARKUP_RUB, DEFAULT_MARKUP_RUB))

    def test_absurd_value_falls_back(self):
        self.assertEqual(load_markups({"P2P_BUY_MARKUP": "900"})[0], DEFAULT_MARKUP_RUB)

    def test_negative_ok(self):
        self.assertEqual(load_markups({"P2P_SELL_MARKUP": "-1"})[1], -1.0)


if __name__ == "__main__":
    unittest.main()
