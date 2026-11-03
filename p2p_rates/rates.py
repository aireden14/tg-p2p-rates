"""Оценка P2P-курса: курс Google (1 USD) плюс постоянная надбавка в рублях."""
import os
from dataclasses import dataclass

# 03.11.2026, срез Bybit: «разумный выбор» (3-е надёжное объявление) 84,00 ₽ при Google 81,50 ₽, то есть около +2,5 ₽.
# Пересчитать надбавку: scripts/calibrate.py. На хостинге переопределяется P2P_BUY_MARKUP / P2P_SELL_MARKUP.
DEFAULT_MARKUP_RUB = 2.5
MAX_ABS_MARKUP = 50.0


@dataclass(frozen=True)
class Estimate:
    buy_price: float      # рублей за 1 USDT при покупке USDT
    sell_price: float     # рублей за 1 USDT при продаже USDT
    usdt_for_rub: float   # сколько USDT получим за amount рублей
    rub_for_usdt: float   # сколько рублей получим за amount USDT


def estimate(amount, google, buy_markup, sell_markup):
    buy, sell = google + buy_markup, google + sell_markup
    return Estimate(buy_price=buy, sell_price=sell, usdt_for_rub=amount / buy, rub_for_usdt=amount * sell)


def _parse(value):
    try:
        number = float(str(value).strip().replace(",", "."))
    except ValueError:
        return None
    return number if abs(number) <= MAX_ABS_MARKUP else None  # nan и бесконечность сюда не проходят


def load_markups(env=None):
    env = os.environ if env is None else env
    buy = _parse(env.get("P2P_BUY_MARKUP", ""))
    sell = _parse(env.get("P2P_SELL_MARKUP", ""))
    return (DEFAULT_MARKUP_RUB if buy is None else buy, DEFAULT_MARKUP_RUB if sell is None else sell)
