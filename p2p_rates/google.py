"""Курс USD/RUB с Google Finance - точка отсчёта, с которой сравниваем P2P-цены."""
import re
import time
import urllib.request

URL = "https://www.google.com/finance/quote/USD-RUB"
MIN_RATE, MAX_RATE = 20.0, 500.0  # вне коридора - значит, разобрали не то число
STALE_AFTER = 3600   # старше часа прежнее значение не показываем
RETRY_AFTER = 60     # после сбоя не долбим Google чаще раза в минуту
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
_PRICE_RE = re.compile(r'class="N6SYTe">\s*<span[^>]*>\s*<span>([0-9][0-9.,]*)</span>')


def parse_usd_rub(html):
    m = _PRICE_RE.search(html or "")
    if not m:
        return None
    raw = m.group(1)
    if "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    else:
        raw = raw.replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if MIN_RATE <= value <= MAX_RATE else None


def _fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=10) as resp:  # URL - константа выше, только https
        return resp.read().decode("utf-8", "replace")


class GoogleRate:
    def __init__(self, fetch=None, ttl=300, clock=time.monotonic):
        self._fetch, self._ttl, self._clock = fetch or _fetch, ttl, clock
        self._value, self._at, self._retry_at = None, 0.0, 0.0

    def usd_rub(self):
        now = self._clock()
        if self._value is not None and now - self._at < self._ttl:
            return self._value
        if now >= self._retry_at:
            try:
                value = parse_usd_rub(self._fetch())
            except Exception:  # курс Google - справка, он не должен ломать бота
                value = None
            if value is not None:
                self._value, self._at = value, now
                return value
            self._retry_at = now + RETRY_AFTER
        if self._value is not None and now - self._at < STALE_AFTER:
            return self._value
        return None
