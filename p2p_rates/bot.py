"""Telegram-бот: клавиатура, настройки чата, кэш курса."""
import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from .bybit import BUY, SELL, BybitError
from .format import fmt_int, parse_amount, render

DEFAULTS = {"amount": 50000, "direction": "both", "bank_only": False}
AMOUNT_PRESETS = (10_000, 50_000, 100_000, 500_000)
DIRECTIONS = ("buy", "sell", "both")
HINT = (
    "Пришлите сумму в рублях (например <b>75000</b>, <b>50к</b> или <b>2 млн</b>) - "
    "покажу актуальный P2P-курс USDT. Кнопка /start открывает панель."
)
BYBIT_DOWN = "⚠️ Bybit сейчас не ответил. Попробуйте через минуту."


class ApiError(Exception):
    pass


class TelegramApi:
    def __init__(self, token):
        self._base = f"https://api.telegram.org/bot{token}/"

    def call(self, method, **params):
        body = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(
            self._base + method, data=body, method="POST", headers={"Content-Type": "application/json"},
        )
        timeout = params.get("timeout", 0) + 20
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as exc:
            try:
                detail = json.load(exc).get("description", "")
            except (ValueError, OSError):
                detail = ""
            raise ApiError(f"{method}: HTTP {exc.code} {detail}".strip()) from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ApiError(f"{method}: {type(exc).__name__}") from None
        if not data.get("ok"):
            raise ApiError(f"{method}: {data.get('description')}")
        return data.get("result")


class Store:
    """Настройки чатов в JSON; запись через временный файл + os.replace."""

    def __init__(self, path):
        self.path = Path(path)
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._data = {}

    def get(self, chat_id):
        return {**DEFAULTS, **self._data.get(str(chat_id), {})}

    def update(self, chat_id, **changes):
        self._data[str(chat_id)] = {**self.get(chat_id), **changes}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".state-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)


class Service:
    """Курс с коротким кэшем, чтобы кнопки не долбили Bybit."""

    def __init__(self, client, ttl=20, clock=time.monotonic):
        self._client, self._ttl, self._clock = client, ttl, clock
        self._cache = {}

    def quote(self, direction, amount, bank_only):
        key = (direction, amount, bank_only)
        hit = self._cache.get(key)
        if hit and self._clock() - hit[0] < self._ttl:
            return hit[1]
        quote = self._client.quote(direction, amount, bank_only=bank_only)
        self._cache[key] = (self._clock(), quote)
        if len(self._cache) > 200:
            self._cache = {k: v for k, v in self._cache.items() if self._clock() - v[0] < self._ttl}
        return quote


def keyboard(settings):
    amount, direction, bank = settings["amount"], settings["direction"], settings["bank_only"]
    amounts = [
        {"text": ("✓ " if amount == a else "") + f"{fmt_int(a // 1000)} тыс", "callback_data": f"amt:{a}"}
        for a in AMOUNT_PRESETS
    ]
    names = {"buy": "🟢 Купить", "sell": "🔴 Продать", "both": "⇅ Оба"}
    dirs = [
        {"text": ("✓ " if direction == d else "") + names[d], "callback_data": f"dir:{d}"} for d in DIRECTIONS
    ]
    tools = [
        {"text": ("☑" if bank else "☐") + " Только банк", "callback_data": "bank"},
        {"text": "🔄 Обновить", "callback_data": "refresh"},
    ]
    return {"inline_keyboard": [amounts, dirs, tools]}


class Bot:
    def __init__(self, api, service, store, google=None):
        self.api, self.service, self.store, self.google = api, service, store, google

    def _compose(self, chat_id):
        s = self.store.get(chat_id)
        try:
            buy = self.service.quote(BUY, s["amount"], s["bank_only"]) if s["direction"] in ("buy", "both") else None
            sell = self.service.quote(SELL, s["amount"], s["bank_only"]) if s["direction"] in ("sell", "both") else None
        except BybitError:
            return BYBIT_DOWN, keyboard(s)
        google = self.google.usd_rub() if self.google else None
        return render(s["amount"], s["direction"], buy, sell, s["bank_only"], google=google), keyboard(s)

    def _send_rates(self, chat_id):
        text, markup = self._compose(chat_id)
        self.api.call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML",
                      reply_markup=markup, disable_web_page_preview=True)

    def handle_update(self, update):
        if "message" in update:
            self._on_message(update["message"])
        elif "callback_query" in update:
            self._on_callback(update["callback_query"])

    def _on_message(self, msg):
        chat_id, text = msg["chat"]["id"], (msg.get("text") or "").strip()
        if not text:
            return
        command = text.split()[0].lower().split("@")[0]
        if command in ("/start", "/help", "/rate", "/kurs", "/курс"):
            amount = parse_amount(text) if len(text.split()) > 1 else None
            if amount:
                self.store.update(chat_id, amount=amount)
            self._send_rates(chat_id)
            return
        amount = parse_amount(text)
        if amount is None:
            self.api.call("sendMessage", chat_id=chat_id, text=HINT, parse_mode="HTML")
            return
        self.store.update(chat_id, amount=amount)
        self._send_rates(chat_id)

    def _on_callback(self, cb):
        chat_id, message_id, data = cb["message"]["chat"]["id"], cb["message"]["message_id"], cb.get("data") or ""
        self.api.call("answerCallbackQuery", callback_query_id=cb["id"])
        kind, _, value = data.partition(":")
        if kind == "amt" and value.isdigit() and int(value) in AMOUNT_PRESETS:
            self.store.update(chat_id, amount=int(value))
        elif kind == "dir" and value in DIRECTIONS:
            self.store.update(chat_id, direction=value)
        elif data == "bank":
            self.store.update(chat_id, bank_only=not self.store.get(chat_id)["bank_only"])
        elif data != "refresh":
            return
        text, markup = self._compose(chat_id)
        try:
            self.api.call("editMessageText", chat_id=chat_id, message_id=message_id, text=text,
                          parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
        except ApiError as exc:
            if "not modified" not in str(exc):
                raise
