import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from p2p_rates.bot import Bot, Store
from p2p_rates.format import render_estimate
from p2p_rates.rates import estimate
from p2p_rates.ref import DEFAULT_REF_URL, load_ref_url, safe_url

NOW = datetime(2026, 11, 4, 9, 0, 0)
REF = "https://www.bybit.com/invite?ref=ABC123&utm=bot"


def text_for(ref_url=None, premium=1.5):
    est = estimate(50_000, 81.5, 2.5, 2.5, premium)
    return render_estimate(50_000, est, 81.5, 2.5, 2.5, now=NOW, premium_pct=premium, ref_url=ref_url)


class SafeUrlTests(unittest.TestCase):
    def test_https_ok(self):
        self.assertEqual(safe_url(REF), REF)

    def test_rejects(self):
        for bad in ("", None, "http://bybit.com/x", "javascript:alert(1)", "ftp://x", "bybit.com",
                    'https://x.com/"onclick="x', "https://x.com/<b>", "https://x.com/a b", "https://" + "a" * 400):
            with self.subTest(bad):
                self.assertIsNone(safe_url(bad))


class LoadRefTests(unittest.TestCase):
    def test_default_is_https_bybit(self):
        self.assertTrue(DEFAULT_REF_URL.startswith("https://") and "bybit.com/" in DEFAULT_REF_URL)
        self.assertEqual(load_ref_url({}), DEFAULT_REF_URL)

    def test_from_env(self):
        self.assertEqual(load_ref_url({"BYBIT_REF_URL": REF}), REF)

    def test_invalid_env_falls_back(self):
        self.assertEqual(load_ref_url({"BYBIT_REF_URL": "http://evil.example"}), DEFAULT_REF_URL)
        self.assertEqual(load_ref_url({"BYBIT_REF_URL": "  "}), DEFAULT_REF_URL)


class RenderRefTests(unittest.TestCase):
    def test_link_is_html_escaped_in_header(self):
        text = text_for(REF)
        self.assertIn('(<a href="https://www.bybit.com/invite?ref=ABC123&amp;utm=bot">Bybit P2P</a>)', text)

    def test_plain_label_without_ref(self):
        text = text_for(None)
        self.assertIn("(Bybit P2P)", text)
        self.assertNotIn("<a ", text)

    def test_unsafe_ref_ignored(self):
        text = text_for("http://insecure.example")
        self.assertIn("(Bybit P2P)", text)
        self.assertNotIn("<a ", text)

    def test_formula_is_not_shown(self):
        text = text_for(REF)
        self.assertNotIn("Google", text)
        self.assertNotIn("+2,50", text)
        self.assertNotIn("%", text)

    def test_no_footer_signature(self):
        text = text_for(REF)
        self.assertNotIn("не живые объявления", text)
        self.assertNotIn("Обновлено", text)
        self.assertNotIn("Пришлите другую сумму", text)
        self.assertTrue(text.rstrip().endswith("₽</b>"))  # последним идёт блок «USDT → ₽»

    def test_prices_unchanged(self):
        text = text_for(REF)
        self.assertIn("85,26", text)
        self.assertIn("586,44 USDT", text)


class FakeGoogle:
    def usd_rub(self):
        return 81.5


class FakeApi:
    def __init__(self):
        self.calls = []

    def call(self, method, **params):
        self.calls.append((method, params))
        return {"message_id": 1}


class BotRefTests(unittest.TestCase):
    def test_bot_puts_ref_link_into_message(self):
        api = FakeApi()
        bot = Bot(api, FakeGoogle(), Store(Path(tempfile.mkdtemp()) / "s.json"), premium_pct=1.5, ref_url=REF)
        bot.handle_update({"update_id": 1, "message": {"message_id": 1, "chat": {"id": 7}, "text": "50000"}})
        sent = [p for m, p in api.calls if m == "sendMessage"][-1]
        self.assertIn('href="https://www.bybit.com/invite?ref=ABC123&amp;utm=bot"', sent["text"])
        self.assertEqual(sent["parse_mode"], "HTML")
        self.assertTrue(sent["disable_web_page_preview"])


if __name__ == "__main__":
    unittest.main()
