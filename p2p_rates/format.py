"""Тексты для Telegram (HTML) и разбор суммы из сообщения."""
import html
import re
from datetime import datetime

MIN_AMOUNT = 500          # меньше Bybit не принимает
MAX_AMOUNT = 3_500_000    # верхний лимит Bybit по рублям

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
