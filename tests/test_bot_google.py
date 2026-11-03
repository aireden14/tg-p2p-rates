import tempfile
import unittest
from pathlib import Path

from p2p_rates.bot import Bot, Service, Store
from p2p_rates.bybit import Ad, Quote
from p2p_rates.selfcheck import check_google


def ad(price):
    return Ad(nick="m", price=price, min_rub=1000.0, max_rub=900000.0, qty_usdt=9999.0,
              payments=("14",), online=True, rate=100.0, orders30=300, national_limit=False)


class FakeClient:
    def quote(self, direction, amount, n=5, bank_only=False):
        base = 83.5 if direction == "buy" else 90.0
        return Quote(ads=[ad(base), ad(base + 0.2), ad(base + 0.4)], reference=base + 0.2)


class FakeApi:
    def __init__(self):
        self.calls = []

    def call(self, method, **params):
        self.calls.append((method, params))
        return {"message_id": 1}


class FakeGoogle:
    def __init__(self, value):
        self.value = value

    def usd_rub(self):
        return self.value


def make_bot(google):
    api = FakeApi()
    store = Store(Path(tempfile.mkdtemp()) / "state.json")
    return Bot(api, Service(FakeClient()), store, google=google), api


def start_text(bot, api):
    bot.handle_update({"update_id": 1, "message": {"message_id": 1, "chat": {"id": 7}, "text": "/start"}})
    return [p for m, p in api.calls if m == "sendMessage"][-1]["text"]


class BotGoogleTests(unittest.TestCase):
    def test_google_rate_and_difference_in_message(self):
        bot, api = make_bot(FakeGoogle(81.48))
        text = start_text(bot, api)
        self.assertIn("1 USD = <b>81,48 ₽</b>", text)
        self.assertIn("+2,5 %", text)  # 83.5 / 81.48 - 1 = +2.48 %

    def test_google_unavailable_message_still_works(self):
        bot, api = make_bot(FakeGoogle(None))
        text = start_text(bot, api)
        self.assertNotIn("Google", text)
        self.assertIn("83,50", text)

    def test_bot_without_google_provider(self):
        bot, api = make_bot(None)
        self.assertIn("83,50", start_text(bot, api))


class CheckGoogleTests(unittest.TestCase):
    def test_ok(self):
        lines = []
        self.assertTrue(check_google(FakeGoogle(81.4847), lines.append))
        self.assertIn("Google: ok", lines[0])
        self.assertIn("81,48", lines[0])

    def test_unavailable(self):
        lines = []
        self.assertFalse(check_google(FakeGoogle(None), lines.append))
        self.assertIn("Google: недоступен", lines[0])


if __name__ == "__main__":
    unittest.main()
