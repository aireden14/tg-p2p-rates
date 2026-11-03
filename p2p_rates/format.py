"""Тексты для Telegram (HTML) и разбор суммы из сообщения."""
import html
import re
from datetime import datetime

from .ref import safe_url

MIN_AMOUNT = 1                  # сумму читаем и как рубли, и как USDT
MAX_AMOUNT = 1_000_000_000      # больше миллиарда - скорее опечатка

_AMOUNT_RE = re.compile(
    r"([0-9][0-9\s ]*(?:[.,][0-9]+)?)\s*(тыс\.?|млн|k|к|m|м)?\s*(?:₽|руб\.?|р\.?|rub)?",
)
_MULT = {"тыс": 1_000, "тыс.": 1_000, "k": 1_000, "к": 1_000, "млн": 1_000_000, "m": 1_000_000, "м": 1_000_000}
_PAY_ICONS = {"14": "🏦", "824": "🏦", "40": "📱", "90": "💵", "18": "💵"}


def fmt_int(value):
    return f"{int(round(value)):,}".replace(",", " ")


def fmt_price(value):
    return f"{value:.2f}".replace(".", ",")


def fmt_usdt(value):
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def fmt_signed(value):
    return f"{value:+.2f}".replace(".", ",")


def fmt_rub(value):
    return fmt_int(value) if abs(value) >= 1000 else f"{value:.2f}".replace(".", ",")


def _source_label(ref_url):
    url = safe_url(ref_url)
    return f'<a href="{html.escape(url, quote=True)}">Bybit P2P</a>' if url else "Bybit P2P"


def render_estimate(amount, est, google, buy_markup, sell_markup, now=None, premium_pct=0.0, ref_url=None):
    """Сумма -> два варианта: эта сумма в рублях -> USDT и такая же сумма USDT -> рубли.

    Формула (Google, надбавка, процент) в тексте не показывается, подпись - «Bybit P2P» со ссылкой.
    """
    label = _source_label(ref_url)
    if buy_markup == sell_markup:
        rate = f"Курс: <b>{fmt_price(est.buy_price)} ₽</b> за 1 USDT ({label})"
    else:
        rate = (f"Курс за 1 USDT: покупка <b>{fmt_price(est.buy_price)} ₽</b>, "
                f"продажа <b>{fmt_price(est.sell_price)} ₽</b> ({label})")
    stamp = (now or datetime.now()).strftime("%H:%M:%S")
    return "\n\n".join([
        "💱 <b>USDT ⇄ рубли</b> · оценка P2P\n" + rate,
        f"🟢 <b>{fmt_int(amount)} ₽ → USDT</b>\nполучите ≈ <b>{fmt_usdt(est.usdt_for_rub)} USDT</b>",
        f"🔴 <b>{fmt_int(amount)} USDT → ₽</b>\nполучите ≈ <b>{fmt_rub(est.rub_for_usdt)} ₽</b>",
        f"<i>Оценка, не живые объявления. Обновлено {stamp}. Пришлите другую сумму - пересчитаю.</i>",
    ])


def render_unavailable():
    return "⚠️ Курс Google сейчас недоступен, оценку посчитать не могу. Попробуйте через минуту."


def fmt_pct(value):
    rounded = round(value, 1)
    if rounded == 0:
        return "0,0 %"
    sign = "+" if rounded > 0 else "-"
    return f"{sign}{abs(rounded):.1f}".replace(".", ",") + " %"


def _premium(price, google):
    return f" ({fmt_pct((price / google - 1) * 100)})" if google else ""


def parse_amount(text):
    """'50к', '1,5 млн', '75 000 руб', '/rate 70000' -> рубли (int) или None."""
    t = re.sub(r"^/\w+(@\w+)?\s*", "", (text or "").strip().lower())
    m = _AMOUNT_RE.fullmatch(t)
    if not m:
        return None
    number = float(re.sub(r"[\s ]", "", m.group(1)).replace(",", "."))
    value = int(round(number * _MULT.get(m.group(2), 1)))
    return value if MIN_AMOUNT <= value <= MAX_AMOUNT else None


def _ad_lines(index, ad, amount, direction, google=None):
    usdt = amount / ad.price
    action = f"получите {fmt_usdt(usdt)} USDT" if direction == "buy" else f"продать {fmt_usdt(usdt)} USDT"
    icons = "".join(dict.fromkeys(_PAY_ICONS.get(p, "") for p in ad.payments)) or "·"
    return (
        f"{index}. <b>{fmt_price(ad.price)} ₽</b>{_premium(ad.price, google)} · {action}\n"
        f"    {html.escape(ad.nick, quote=False)} · {ad.rate:.0f}% · {ad.orders30} сд. · "
        f"{fmt_int(ad.min_rub)}-{fmt_int(ad.max_rub)} ₽ · {icons}"
    )


def _block(title, quote, amount, direction, google=None):
    lines = [f"<b>{title}</b>"]
    if quote is None or not quote.ads:
        lines.append("нет подходящих объявлений на эту сумму")
        return "\n".join(lines)
    lines += [_ad_lines(i, a, amount, direction, google) for i, a in enumerate(quote.ads, 1)]
    if quote.reference is not None:
        lines.append(f"Ориентир (медиана лучших 10): <b>{fmt_price(quote.reference)} ₽</b>{_premium(quote.reference, google)}")
    if len(quote.ads) >= 3:
        pick = quote.ads[2]
        edge = "дешёвое" if direction == "buy" else "высокое"
        lines.append(
            f"👉 Разумный выбор: <b>{fmt_price(pick.price)} ₽</b>{_premium(pick.price, google)} - "
            f"не самое {edge}, а 3-е надёжное"
        )
    return "\n".join(lines)


def render(amount, direction, buy, sell, bank_only, now=None, google=None):
    head = [
        "💱 <b>USDT ⇄ рубли · P2P Bybit</b>",
        f"Сумма: <b>{fmt_int(amount)} ₽</b>" + (" · только банковский перевод" if bank_only else ""),
    ]
    if google:
        head.append(f"Google: 1 USD = <b>{fmt_price(google)} ₽</b> (в скобках - разница с ним)")
    parts = ["\n".join(head)]
    if direction in ("buy", "both"):
        parts.append(_block("🟢 Рубли → USDT (купить USDT)", buy, amount, "buy", google))
    if direction in ("sell", "both"):
        parts.append(_block("🔴 USDT → рубли (продать USDT)", sell, amount, "sell", google))
    if buy and sell and buy.ads and sell.ads and sell.ads[0].price > buy.ads[0].price:
        parts.append(
            "⚠️ Цена продажи выше цены покупки: объявления Bybit сейчас не сходятся между собой. "
            "Перед сделкой проверьте условия и лимиты в самом объявлении."
        )
    stamp = (now or datetime.now()).strftime("%H:%M:%S")
    parts.append(f"<i>Обновлено {stamp}. Пришлите сумму в рублях, например 75000 или 2 млн.</i>")
    return "\n\n".join(parts)
