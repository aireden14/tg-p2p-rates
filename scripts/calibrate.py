"""Пересчёт надбавки к Google: сколько рублей сверх курса Google просят надёжные продавцы Bybit.

Запускать на Маке (с серверов хостингов Bybit даёт 403):
    cd ~/services/tg-p2p-rates && python3 scripts/calibrate.py
Результат - число для P2P_BUY_MARKUP (или DEFAULT_MARKUP_RUB в p2p_rates/rates.py).
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from p2p_rates import bybit  # noqa: E402
from p2p_rates.bybit import BUY  # noqa: E402
from p2p_rates.google import GoogleRate  # noqa: E402

AMOUNTS = (10_000, 50_000, 100_000)


def reliable_prices(amount, pages=4):
    ads = []
    for page in range(1, pages + 1):
        got, total = bybit.parse_items(bybit._http_post(bybit.build_request(BUY, amount, page)))
        ads += got
        if page * bybit.PAGE_SIZE >= total or not got:
            break
    return sorted(a.price for a in ads if bybit.is_reliable(a, amount))


def main():
    google = GoogleRate().usd_rub()
    if google is None:
        print("Google недоступен, пересчитать нельзя")
        return 1
    print(f"Google: 1 USD = {google:.2f} ₽")
    picks = []
    for amount in AMOUNTS:
        prices = reliable_prices(amount)
        if len(prices) < 3:
            print(f"  {amount:>9,} ₽: надёжных объявлений мало ({len(prices)}), пропускаю".replace(",", " "))
            continue
        pick = prices[2]  # 3-е надёжное: не самое дешёвое
        picks.append(pick - google)
        print(f"  {amount:>9,} ₽: 1-е {prices[0]:.2f}, 3-е {pick:.2f} (+{pick - google:.2f} ₽ к Google, {len(prices)} надёжных)".replace(",", " "))
    if not picks:
        print("данных нет")
        return 1
    print(f"Рекомендуемая надбавка (медиана по суммам): +{statistics.median(picks):.2f} ₽")
    return 0


if __name__ == "__main__":
    sys.exit(main())
