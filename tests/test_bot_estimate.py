import json
import tempfile
import unittest
from pathlib import Path

from p2p_rates.bot import ApiError, Bot, Store


class FakeGoogle:
    def __init__(self, value=81.5):
        self.value, self.calls = value, 0

    def usd_rub(self):
        self.calls += 1
        return self.value


class FakeApi:
    def __init__(self, edit_error=None):
        self.calls, self.edit_error = [], edit_error

    def call(self, method, **params):
        self.calls.append((method, params))
        if method == "editMessageText" and self.edit_error:
            raise self.edit_error
        return {"message_id": 1}

    def methods(self):
        return [m for m, _ in self.calls]

    def last(self, method):
        return [p for m, p in self.calls if m == method][-1]


def make_bot(google=None, buy=2.5, sell=2.5, edit_error=None):
    google = google or FakeGoogle()
    api = FakeApi(edit_error)
    store = Store(Path(tempfile.mkdtemp()) / "state.json")
    return Bot(api, google, store, buy_markup=buy, sell_markup=sell), api, google, store


def message(text, chat=7):
    return {"update_id": 1, "message": {"message_id": 5, "chat": {"id": chat}, "text": text}}


def callback(data, chat=7, mid=11):
    return {"update_id": 2, "callback_query": {
        "id": "cb1", "data": data, "message": {"message_id": mid, "chat": {"id": chat}}}}


class BotEstimateTests(unittest.TestCase):
    def test_start_shows_both_variants_for_default_amount(self):
        bot, api, _, _ = make_bot()
        bot.handle_update(message("/start"))
        sent = api.last("sendMessage")
        self.assertEqual(sent["parse_mode"], "HTML")
        self.assertIn("50 000 ₽ → USDT", sent["text"])
        self.assertIn("50 000 USDT → ₽", sent["text"])
        flat = [b["callback_data"] for r in sent["reply_markup"]["inline_keyboard"] for b in r]
        for needed in ("amt:10000", "amt:50000", "amt:100000", "amt:500000", "amt:1000000", "refresh"):
            self.assertIn(needed, flat)

    def test_number_gives_both_variants(self):
        bot, api, _, store = make_bot()
        bot.handle_update(message("75 000"))
        text = api.last("sendMessage")["text"]
        self.assertIn("75 000 ₽ → USDT", text)
        self.assertIn("75 000 USDT → ₽", text)
        self.assertIn("892,86 USDT", text)       # 75000 / 84
        self.assertIn("6 300 000 ₽", text)       # 75000 * 84
        self.assertEqual(store.get(7)["amount"], 75_000)

    def test_k_and_million_suffixes(self):
        bot, api, _, store = make_bot()
        bot.handle_update(message("2 млн"))
        self.assertEqual(store.get(7)["amount"], 2_000_000)

    def test_rate_command_with_amount(self):
        bot, api, _, store = make_bot()
        bot.handle_update(message("/rate 120000"))
        self.assertEqual(store.get(7)["amount"], 120_000)
        self.assertIn("120 000 ₽ → USDT", api.last("sendMessage")["text"])

    def test_garbage_gets_hint_and_no_google_call(self):
        bot, api, google, _ = make_bot()
        bot.handle_update(message("ляляля"))
        self.assertIn("сумм", api.last("sendMessage")["text"].lower())
        self.assertEqual(google.calls, 0)

    def test_callback_changes_amount_and_edits_message(self):
        bot, api, _, store = make_bot()
        bot.handle_update(callback("amt:100000"))
        self.assertIn("answerCallbackQuery", api.methods())
        edit = api.last("editMessageText")
        self.assertEqual(edit["message_id"], 11)
        self.assertIn("100 000 ₽ → USDT", edit["text"])
        self.assertEqual(store.get(7)["amount"], 100_000)

    def test_refresh(self):
        bot, api, _, _ = make_bot()
        bot.handle_update(callback("refresh"))
        self.assertIn("editMessageText", api.methods())

    def test_different_markups_change_numbers(self):
        bot, api, _, _ = make_bot(buy=3.0, sell=1.0)
        bot.handle_update(message("10000"))
        text = api.last("sendMessage")["text"]
        self.assertIn("84,50", text)
        self.assertIn("82,50", text)
        self.assertIn("825 000 ₽", text)  # 10000 * 82.5

    def test_google_unavailable_is_friendly(self):
        bot, api, _, _ = make_bot(google=FakeGoogle(None))
        bot.handle_update(message("/start"))
        text = api.last("sendMessage")["text"]
        self.assertIn("Google", text)
        self.assertNotIn("≈", text)
        self.assertNotIn("Traceback", text)

    def test_unknown_callback_ignored(self):
        bot, api, _, _ = make_bot()
        bot.handle_update(callback("zzz:1"))
        self.assertEqual(api.methods(), ["answerCallbackQuery"])

    def test_message_not_modified_is_swallowed(self):
        err = ApiError("editMessageText: HTTP 400 Bad Request: message is not modified")
        bot, api, _, _ = make_bot(edit_error=err)
        bot.handle_update(callback("refresh"))  # не должно бросить

    def test_store_survives_reload(self):
        _, _, _, store = make_bot()
        store.update(7, amount=12_345)
        self.assertEqual(Store(store.path).get(7)["amount"], 12_345)
        json.loads(Path(store.path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
