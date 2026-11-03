"""Telegram-бот: пишешь сумму - получаешь два варианта обмена по формуле «Google + надбавка»."""
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from .format import fmt_int, parse_amount, render_estimate, render_unavailable
from .rates import DEFAULT_MARKUP_RUB, estimate

DEFAULTS = {"amount": 50000}
AMOUNT_PRESETS = (10_000, 50_000, 100_000, 500_000, 1_000_000)
HINT = (
    "Пришлите сумму (например <b>50000</b>, <b>50к</b> или <b>2 млн</b>) - покажу оба варианта: "
    "эта сумма в рублях → USDT и такая же сумма в USDT → рубли. Кнопка /start открывает панель."
)


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
    """Последняя сумма каждого чата в JSON; запись через временный файл + os.replace."""

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


def keyboard(amount):
    def button(value):
        return {"text": ("✓ " if amount == value else "") + fmt_int(value), "callback_data": f"amt:{value}"}

    first = [button(v) for v in AMOUNT_PRESETS[:3]]
    second = [button(v) for v in AMOUNT_PRESETS[3:]] + [{"text": "🔄 Обновить", "callback_data": "refresh"}]
    return {"inline_keyboard": [first, second]}


class Bot:
    def __init__(self, api, google, store, buy_markup=DEFAULT_MARKUP_RUB, sell_markup=DEFAULT_MARKUP_RUB):
        self.api, self.google, self.store = api, google, store
        self.buy_markup, self.sell_markup = buy_markup, sell_markup

    def _compose(self, chat_id):
        amount = self.store.get(chat_id)["amount"]
        rate = self.google.usd_rub()
        markup = keyboard(amount)
        if rate is None:
            return render_unavailable(), markup
        est = estimate(amount, rate, self.buy_markup, self.sell_markup)
        return render_estimate(amount, est, rate, self.buy_markup, self.sell_markup), markup

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
        elif data != "refresh":
            return
        text, markup = self._compose(chat_id)
        try:
            self.api.call("editMessageText", chat_id=chat_id, message_id=message_id, text=text,
                          parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
        except ApiError as exc:
            if "not modified" not in str(exc):
                raise
