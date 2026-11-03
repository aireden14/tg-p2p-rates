import json
import unittest
from pathlib import Path

from p2p_rates import bybit
from p2p_rates.bybit import Ad, BUY, SELL, BybitError

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def ad(**kw):
    base = dict(
        nick="t", price=90.0, min_rub=1000.0, max_rub=100000.0, qty_usdt=5000.0,
        payments=("14",), online=True, rate=100.0, orders30=100, national_limit=False,
    )
    base.update(kw)
    return Ad(**base)


class ParseTests(unittest.TestCase):
    def test_parse_fixture_page(self):
        ads, total = bybit.parse_items(load("bybit_side1_amount50000_p1.json"))
        self.assertEqual(len(ads), 20)
        self.assertGreater(total, 20)
        first = ads[0]
        self.assertIsInstance(first.price, float)
        self.assertEqual(first.price, 82.20)
        self.assertEqual(first.min_rub, 500.0)
        self.assertEqual(first.max_rub, 90000.0)
        self.assertIn("14", first.payments)
        self.assertFalse(first.online)
        self.assertEqual(first.rate, 100.0)
        self.assertEqual(first.orders30, 299)

    def test_parse_error_payload(self):
        with self.assertRaises(BybitError):
            bybit.parse_items({"ret_code": 10001, "ret_msg": "boom", "result": {}})

    def test_parse_empty_result(self):
        ads, total = bybit.parse_items({"ret_code": 0, "ret_msg": "SUCCESS", "result": {"count": 0, "items": []}})
        self.assertEqual((ads, total), ([], 0))

    def test_national_limit_flag(self):
        payload = {"ret_code": 0, "result": {"count": 1, "items": [{
            "nickName": "x", "price": "90.00", "minAmount": "500", "maxAmount": "9000",
            "lastQuantity": "10", "payments": ["14"], "isOnline": True,
            "recentExecuteRate": 99, "recentOrderNum": 50,
            "tradingPreferenceSet": {"hasNationalLimit": 1, "nationalLimit": "BRN"},
        }]}}
        ads, _ = bybit.parse_items(payload)
        self.assertTrue(ads[0].national_limit)


class ReliableTests(unittest.TestCase):
    def test_good_ad_passes(self):
        self.assertTrue(bybit.is_reliable(ad(), 50000))

    def test_rejects(self):
        cases = {
            "offline": ad(online=False),
            "low rate": ad(rate=90.0),
            "few orders": ad(orders30=10),
            "national": ad(national_limit=True),
            "below min": ad(min_rub=60000.0),
            "above max": ad(max_rub=40000.0),
            "no volume": ad(qty_usdt=100.0),
        }
        for name, a in cases.items():
            with self.subTest(name):
                self.assertFalse(bybit.is_reliable(a, 50000))

    def test_bank_only(self):
        cash = ad(payments=("90",))
        self.assertTrue(bybit.is_reliable(cash, 50000))
        self.assertFalse(bybit.is_reliable(cash, 50000, bank_only=True))
        self.assertTrue(bybit.is_reliable(ad(payments=("14", "40")), 50000, bank_only=True))


class RankTests(unittest.TestCase):
    def test_buy_is_ascending_sell_is_descending(self):
        ads = [ad(nick="a", price=90), ad(nick="b", price=85), ad(nick="c", price=95)]
        self.assertEqual([x.nick for x in bybit.best_ads(ads, BUY, 50000)], ["b", "a", "c"])
        self.assertEqual([x.nick for x in bybit.best_ads(ads, SELL, 50000)], ["c", "a", "b"])

    def test_limit_n(self):
        ads = [ad(nick=str(i), price=80 + i) for i in range(10)]
        self.assertEqual(len(bybit.best_ads(ads, BUY, 50000, n=3)), 3)

    def test_reference_is_median_of_first_ten(self):
        prices = [80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 200]
        ads = [ad(price=p) for p in prices]
        self.assertAlmostEqual(bybit.reference_price(bybit.best_ads(ads, BUY, 50000, n=10)), 84.5)

    def test_reference_empty(self):
        self.assertIsNone(bybit.reference_price([]))

    def test_fixtures_give_sane_order(self):
        buy, _ = bybit.parse_items(load("bybit_side1_amount50000_p1.json"))
        top = bybit.best_ads(buy, BUY, 50000, n=5)
        self.assertTrue(top)
        prices = [a.price for a in top]
        self.assertEqual(prices, sorted(prices))
        self.assertTrue(all(a.online and a.rate >= bybit.MIN_RATE for a in top))
        sell, _ = bybit.parse_items(load("bybit_side0_amount50000_p1.json"))
        top = bybit.best_ads(sell, SELL, 50000, n=5)
        prices = [a.price for a in top]
        self.assertEqual(prices, sorted(prices, reverse=True))


class ClientTests(unittest.TestCase):
    def test_request_body_directions(self):
        buy = bybit.build_request(BUY, 50000, page=1, size=100)
        sell = bybit.build_request(SELL, 50000, page=2, size=100)
        self.assertEqual(buy["side"], "1")
        self.assertEqual(sell["side"], "0")
        self.assertEqual(buy["tokenId"], "USDT")
        self.assertEqual(buy["currencyId"], "RUB")
        self.assertEqual(buy["amount"], "50000")
        self.assertEqual(sell["page"], "2")

    def test_client_stops_when_enough_reliable(self):
        calls = []
        page = load("bybit_side1_amount50000_p1.json")

        def post(body):
            calls.append(body)
            return page

        client = bybit.BybitClient(post=post)
        quote = client.quote(BUY, 50000, n=3)
        self.assertEqual(len(quote.ads), 3)
        self.assertIsNotNone(quote.reference)
        self.assertLessEqual(len(calls), 5)

    def test_client_paginates_until_exhausted(self):
        calls = []

        def post(body):
            calls.append(body["page"])
            return {"ret_code": 0, "result": {"count": 250, "items": []}}

        client = bybit.BybitClient(post=post)
        quote = client.quote(BUY, 50000)
        self.assertEqual(quote.ads, [])
        self.assertIsNone(quote.reference)
        self.assertEqual(calls, ["1"])

    def test_client_propagates_error(self):
        client = bybit.BybitClient(post=lambda body: {"ret_code": 1, "ret_msg": "x"})
        with self.assertRaises(BybitError):
            client.quote(BUY, 50000)


if __name__ == "__main__":
    unittest.main()
