"""Проверка при старте: видно в логе хостинга, достижимы ли Bybit и Telegram."""
from .bot import ApiError
from .bybit import BUY, SELL, BybitError
from .format import fmt_price

CHECK_AMOUNT = 50_000


def check_bybit(client, log):
    try:
        buy = client.quote(BUY, CHECK_AMOUNT)
        sell = client.quote(SELL, CHECK_AMOUNT)
    except BybitError as exc:
        log(f"Bybit: недоступен ({exc})")
        return False
    if not buy.ads or not sell.ads:
        log("Bybit: ответил, но нет объявлений на 50 000 ₽")
        return False
    log(f"Bybit: ok, покупка {fmt_price(buy.ads[0].price)} ₽, продажа {fmt_price(sell.ads[0].price)} ₽")
    return True


def check_telegram(api, log):
    try:
        me = api.call("getMe")
    except ApiError as exc:
        log(f"Telegram: {exc}")
        return False
    log(f"Telegram: ok, @{me.get('username')}")
    return True
