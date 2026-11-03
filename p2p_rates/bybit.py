"""P2P Bybit, пара USDT/RUB: разбор объявлений, отбор надёжных, выбор лучших цен.

side=1 у Bybit - купить USDT за рубли (выдача от дешёвых), side=0 - продать USDT (от дорогих).
"""
import json
import statistics
import urllib.error
import urllib.request
from dataclasses import dataclass, field

URL = "https://api2.bybit.com/fiat/otc/item/online"
BUY, SELL = "buy", "sell"
SIDE_PARAM = {BUY: "1", SELL: "0"}

MIN_RATE = 95.0       # % выполненных сделок за 30 дней
MIN_ORDERS = 30       # сделок за 30 дней
BANK_IDS = {"14", "824"}  # Bank Transfer, Bank Transfer (API)
PAGE_SIZE = 100
MAX_PAGES = 5
REFERENCE_DEPTH = 10  # ориентир - медиана стольких лучших надёжных объявлений


class BybitError(Exception):
    pass


@dataclass(frozen=True)
class Ad:
    nick: str
    price: float
    min_rub: float
    max_rub: float
    qty_usdt: float
    payments: tuple
    online: bool
    rate: float
    orders30: int
    national_limit: bool
    ad_id: str = ""


@dataclass
class Quote:
    ads: list = field(default_factory=list)
    reference: float = None


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_items(payload):
    """Ответ Bybit -> (список Ad, всего объявлений по запросу)."""
    if payload.get("ret_code") != 0:
        raise BybitError(f"Bybit ответил ошибкой: {payload.get('ret_msg') or payload.get('ret_code')}")
    result = payload.get("result") or {}
    ads = []
    for item in result.get("items") or []:
        price = _num(item.get("price"), None)
        if not price:
            continue
        prefs = item.get("tradingPreferenceSet") or {}
        ads.append(Ad(
            nick=str(item.get("nickName") or "?"),
            price=price,
            min_rub=_num(item.get("minAmount")),
            max_rub=_num(item.get("maxAmount")),
            qty_usdt=_num(item.get("lastQuantity")),
            payments=tuple(str(p) for p in item.get("payments") or []),
            online=bool(item.get("isOnline")),
            rate=_num(item.get("recentExecuteRate")),
            orders30=int(_num(item.get("recentOrderNum"))),
            national_limit=bool(prefs.get("hasNationalLimit")),
            ad_id=str(item.get("id") or ""),
        ))
    return ads, int(_num(result.get("count")))


def is_reliable(ad, amount_rub, bank_only=False):
    if not ad.online or ad.rate < MIN_RATE or ad.orders30 < MIN_ORDERS or ad.national_limit:
        return False
    if not ad.min_rub <= amount_rub <= ad.max_rub:
        return False
    if ad.qty_usdt * ad.price < amount_rub:
        return False
    if bank_only and not BANK_IDS.intersection(ad.payments):
        return False
    return True


def best_ads(ads, direction, amount_rub, n=5, bank_only=False):
    good = [a for a in ads if is_reliable(a, amount_rub, bank_only)]
    if direction == BUY:
        good.sort(key=lambda a: (a.price, -a.orders30))
    else:
        good.sort(key=lambda a: (-a.price, -a.orders30))
    return good[:n]


def reference_price(ads):
    prices = [a.price for a in ads[:REFERENCE_DEPTH]]
    return statistics.median(prices) if prices else None


def build_request(direction, amount_rub, page, size=PAGE_SIZE):
    return {
        "userId": "", "tokenId": "USDT", "currencyId": "RUB", "payment": [],
        "side": SIDE_PARAM[direction], "size": str(size), "page": str(page),
        "amount": str(int(amount_rub)), "authMaker": False, "canTrade": False,
    }


def _http_post(body, timeout=15):
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        try:
            snippet = exc.read(120).decode("utf-8", "replace").replace("\n", " ").strip()
        except (OSError, ValueError):
            snippet = ""
        raise BybitError(f"Bybit недоступен: HTTP {exc.code} {snippet}".strip()) from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise BybitError(f"Bybit недоступен: {type(exc).__name__}") from exc


class BybitClient:
    def __init__(self, post=None):
        self._post = post or _http_post

    def quote(self, direction, amount_rub, n=5, bank_only=False, max_pages=MAX_PAGES):
        seen, collected = set(), []
        for page in range(1, max_pages + 1):
            ads, total = parse_items(self._post(build_request(direction, amount_rub, page)))
            fresh = [a for a in ads if not a.ad_id or a.ad_id not in seen]
            seen.update(a.ad_id for a in fresh if a.ad_id)
            collected.extend(fresh)
            enough = len(best_ads(collected, direction, amount_rub, REFERENCE_DEPTH, bank_only)) >= REFERENCE_DEPTH
            if enough or not fresh or page * PAGE_SIZE >= total:
                break
        best = best_ads(collected, direction, amount_rub, REFERENCE_DEPTH, bank_only)
        return Quote(ads=best[:n], reference=reference_price(best))
