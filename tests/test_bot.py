import json
import tempfile
import unittest
from pathlib import Path

from p2p_rates.bot import Bot, Service, Store
from p2p_rates.bybit import Ad, Quote, BybitError, BUY, SELL


def ad(price, nick="Trader"):
    return Ad(nick=nick, price=price, min_rub=1000.0, max_rub=900000.0, qty_usdt=9999.0,
              payments=("14",), online=True, rate=100.0, orders30=100, national_limit=False)


class FakeClient:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def quote(self, direction, amount, n=5, bank_only=False):
        self.calls.append((direction, amount, bank_only))
        if self.fail:
            raise BybitError("down")
        price = 82.35 if direction == BUY else 80.0
        return Quote(ads=[ad(price)], reference=price)


class FakeApi:
    def __init__(self):
        self.calls = []

    def call(self, method, **params):
        self.calls.append((method, params))
        return {"message_id": 1}

    def methods(self):
        return [m for m, _ in self.calls]


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def make_bot(fail=False):
    tmp = tempfile.mkdtemp()
    client = FakeClient(fail=fail)
    clock = FakeClock()
    service = Service(client, ttl=20, clock=clock)
    store = Store(Path(tmp) / "state.json")
    api = FakeApi()
    return Bot(api, service, store), api, client, clock, store


def message(text, chat=7):
    return {"update_id": 1, "message": {"message_id": 5, "chat": {"id": chat}, "text": text}}


def callback(data, chat=7, mid=11):
    return {"update_id": 2, "callback_query": {
        "id": "cb1", "data": data, "message": {"message_id": mid, "chat": {"id": chat}}}}


class BotTests(unittest.TestCase):
    def test_start_shows_rates_with_keyboard(self):
        bot, api, client, _, _ = make_bot()
        bot.handle_update(message("/start"))
        self.assertIn("sendMessage", api.methods())
        method, params = [c for c in api.calls if c[0] == "sendMessage"][-1]
        self.assertEqual(params["chat_id"], 7)
        self.assertEqual(params["parse_mode"], "HTML")
        self.assertIn("82,35", params["text"])
        rows = params["reply_markup"]["inline_keyboard"]
        flat = [b["callback_data"] for r in rows for b in r]
        for needed in ("amt:10000", "amt:100000", "dir:buy", "dir:sell", "dir:both", "bank", "refresh"):
            self.assertIn(needed, flat)

    def test_number_sets_amount(self):
        bot, api, client, _, store = make_bot()
        bot.handle_update(message("75 000"))
        self.assertEqual(store.get(7)["amount"], 75000)
        self.assertTrue(all(c[1] == 75000 for c in client.calls))

    def test_garbage_text_gets_hint_not_crash(self):
        bot, api, client, _, _ = make_bot()
        bot.handle_update(message("ляляля"))
        method, params = api.calls[-1]
        self.assertEqual(method, "sendMessage")
        self.assertIn("сумм", params["text"].lower())
        self.assertEqual(client.calls, [])

    def test_callback_edits_message_and_answers(self):
        bot, api, client, _, store = make_bot()
        bot.handle_update(callback("amt:100000"))
        self.assertIn("editMessageText", api.methods())
        self.assertIn("answerCallbackQuery", api.methods())
        edit = [p for m, p in api.calls if m == "editMessageText"][-1]
        self.assertEqual(edit["message_id"], 11)
        self.assertEqual(store.get(7)["amount"], 100000)

    def test_direction_and_bank_toggle(self):
        bot, api, client, _, store = make_bot()
        bot.handle_update(callback("dir:sell"))
        self.assertEqual(store.get(7)["direction"], "sell")
        bot.handle_update(callback("bank"))
        self.assertTrue(store.get(7)["bank_only"])
        bot.handle_update(callback("bank"))
        self.assertFalse(store.get(7)["bank_only"])

    def test_cache_within_ttl(self):
        bot, api, client, clock, _ = make_bot()
        bot.handle_update(message("/start"))
        n = len(client.calls)
        clock.t = 10
        bot.handle_update(callback("refresh"))
        self.assertEqual(len(client.calls), n)
        clock.t = 30
        bot.handle_update(callback("refresh"))
        self.assertGreater(len(client.calls), n)

    def test_bybit_error_gives_friendly_message(self):
        bot, api, client, _, _ = make_bot(fail=True)
        bot.handle_update(message("/start"))
        method, params = [c for c in api.calls if c[0] == "sendMessage"][-1]
        self.assertIn("Bybit", params["text"])
        self.assertNotIn("Traceback", params["text"])

    def test_unknown_callback_is_ignored(self):
        bot, api, client, _, _ = make_bot()
        bot.handle_update(callback("zzz:1"))
        self.assertEqual(api.methods(), ["answerCallbackQuery"])

    def test_store_survives_reload(self):
        bot, api, client, _, store = make_bot()
        store.update(7, amount=12345)
        again = Store(store.path)
        self.assertEqual(again.get(7)["amount"], 12345)
        json.loads(Path(store.path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
