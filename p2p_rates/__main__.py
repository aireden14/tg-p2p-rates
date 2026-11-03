"""Запуск: python3 -m p2p_rates  (токен - TELEGRAM_BOT_TOKEN или файл .env рядом)."""
import os
import sys
import time
import traceback
from pathlib import Path

from .bot import ApiError, Bot, Store, TelegramApi
from .google import GoogleRate
from .keepalive import start_health_server, start_self_ping
from .rates import load_markups, load_premium
from .selfcheck import check_google, check_telegram

ROOT = Path(__file__).resolve().parent.parent
COMMANDS = [
    {"command": "start", "description": "Курс USDT/рубли сейчас"},
    {"command": "rate", "description": "Курс на сумму, например /rate 75000"},
]


def log(message):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), message, flush=True)


def load_token():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if token:
        return token
    try:
        for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "TELEGRAM_BOT_TOKEN" and value.strip():
                return value.strip().strip("\"'")
    except OSError:
        pass
    return ""


def wait_for_token():
    warned = False
    while True:
        token = load_token()
        if token:
            return token
        if not warned:
            log("Нет токена: положите TELEGRAM_BOT_TOKEN в .env рядом с программой. Жду.")
            warned = True
        time.sleep(30)


def start_hosting_helpers():
    """На хостинге (Render) задан PORT: открываем /health и не даём сервису уснуть."""
    port = os.environ.get("PORT", "").strip()
    if not port.isdigit():
        return
    start_health_server(int(port))
    log(f"Health-сервер на порту {port}")
    if start_self_ping(os.environ.get("RENDER_EXTERNAL_URL", "")):
        log("Самопинг включён")


def selfcheck_only():
    """SELFCHECK_ONLY=1: только проверить Google с этого хостинга и ждать (Telegram не трогаем)."""
    check_google(GoogleRate(), log)
    while True:
        time.sleep(3600)


def main():
    start_hosting_helpers()
    if os.environ.get("SELFCHECK_ONLY"):
        selfcheck_only()
    api = TelegramApi(wait_for_token())
    google = GoogleRate()
    buy_markup, sell_markup = load_markups()
    premium_pct = load_premium()
    bot = Bot(api, google, Store(ROOT / "state.json"), buy_markup=buy_markup, sell_markup=sell_markup,
              premium_pct=premium_pct)
    check_telegram(api, log)
    check_google(google, log)
    log(f"Надбавка к Google, ₽: покупка {buy_markup:+.2f}, продажа {sell_markup:+.2f}; сверху {premium_pct:+.1f} %")
    try:
        api.call("setMyCommands", commands=COMMANDS)
    except ApiError as exc:
        log(f"setMyCommands не вышло: {exc}")
    log("Бот запущен")
    offset, backoff = None, 1
    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message", "callback_query"]}
            if offset is not None:
                params["offset"] = offset
            updates = api.call("getUpdates", **params)
            backoff = 1
        except KeyboardInterrupt:
            return 0
        except ApiError as exc:
            log(f"Telegram: {exc}; повтор через {backoff} с")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue
        for update in updates:
            offset = update["update_id"] + 1
            try:
                bot.handle_update(update)
            except Exception:  # один сбойный апдейт не должен ронять бота
                log("Ошибка обработки апдейта:\n" + traceback.format_exc(limit=3))


if __name__ == "__main__":
    sys.exit(main())
