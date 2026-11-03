import unittest

from p2p_rates.bybit import Ad, BybitError, Quote
from p2p_rates.selfcheck import check_bybit, check_telegram
from p2p_rates.bot import ApiError


def ad(price):
    return Ad(nick="m", price=price, min_rub=1000.0, max_rub=900000.0, qty_usdt=9999.0,
              payments=("14",), online=True, rate=100.0, orders30=100, national_limit=False)


class FakeClient:
    def __init__(self, fail=False, empty=False):
        self.fail, self.empty = fail, empty

    def quote(self, direction, amount, n=5, bank_only=False):
        if self.fail:
            raise BybitError("Bybit недоступен: URLError")
        if self.empty:
            return Quote(ads=[], reference=None)
        return Quote(ads=[ad(82.35 if direction == "buy" else 93.5)], reference=84.1)


class BybitCheckTests(unittest.TestCase):
    def test_logs_both_prices(self):
        lines = []
        self.assertTrue(check_bybit(FakeClient(), lines.append))
        self.assertEqual(len(lines), 1)
        self.assertIn("Bybit: ok", lines[0])
        self.assertIn("82,35", lines[0])
        self.assertIn("93,50", lines[0])

    def test_failure_is_logged_not_raised(self):
        lines = []
        self.assertFalse(check_bybit(FakeClient(fail=True), lines.append))
        self.assertIn("Bybit: недоступен", lines[0])

    def test_empty_answer_is_reported(self):
        lines = []
        self.assertFalse(check_bybit(FakeClient(empty=True), lines.append))
        self.assertIn("нет объявлений", lines[0])


class TelegramCheckTests(unittest.TestCase):
    class Api:
        def __init__(self, fail=False):
            self.fail = fail

        def call(self, method, **params):
            if self.fail:
                raise ApiError("getMe: HTTP 401 Unauthorized")
            return {"username": "Checkp2pbot"}

    def test_ok(self):
        lines = []
        self.assertTrue(check_telegram(self.Api(), lines.append))
        self.assertIn("@Checkp2pbot", lines[0])

    def test_bad_token_is_logged(self):
        lines = []
        self.assertFalse(check_telegram(self.Api(fail=True), lines.append))
        self.assertIn("401", lines[0])


if __name__ == "__main__":
    unittest.main()
