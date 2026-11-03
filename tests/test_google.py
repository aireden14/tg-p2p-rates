import unittest
from pathlib import Path

from p2p_rates.google import GoogleRate, parse_usd_rub

FIX = Path(__file__).parent / "fixtures"


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class ParseTests(unittest.TestCase):
    def test_real_page_fragment(self):
        html = (FIX / "google_usd_rub_snippet.html").read_text(encoding="utf-8")
        self.assertAlmostEqual(parse_usd_rub(html), 81.4847)

    def test_decimal_comma(self):
        html = '<div class="N6SYTe"><span jsname="Pdsbrc" class=""><span>81,4847</span></span></div>'
        self.assertAlmostEqual(parse_usd_rub(html), 81.4847)

    def test_thousands_separator_ignored(self):
        html = '<div class="N6SYTe"><span jsname="Pdsbrc" class=""><span>1,081.25</span></span></div>'
        self.assertIsNone(parse_usd_rub(html))  # вне разумного коридора курса

    def test_not_found(self):
        self.assertIsNone(parse_usd_rub("<html>нет цены</html>"))
        self.assertIsNone(parse_usd_rub(""))

    def test_absurd_value_rejected(self):
        html = '<div class="N6SYTe"><span jsname="Pdsbrc" class=""><span>0.5</span></span></div>'
        self.assertIsNone(parse_usd_rub(html))


class CacheTests(unittest.TestCase):
    PAGE = '<div class="N6SYTe"><span jsname="Pdsbrc" class=""><span>81.50</span></span></div>'

    def test_cached_within_ttl(self):
        calls, clock = [], FakeClock()
        g = GoogleRate(fetch=lambda: calls.append(1) or self.PAGE, ttl=300, clock=clock)
        self.assertEqual(g.usd_rub(), 81.5)
        clock.t = 100
        self.assertEqual(g.usd_rub(), 81.5)
        self.assertEqual(len(calls), 1)
        clock.t = 400
        g.usd_rub()
        self.assertEqual(len(calls), 2)

    def test_failure_returns_none(self):
        def boom():
            raise OSError("down")

        self.assertIsNone(GoogleRate(fetch=boom, ttl=300, clock=FakeClock()).usd_rub())

    def test_failure_keeps_last_good_value(self):
        clock, state = FakeClock(), {"ok": True}

        def fetch():
            if state["ok"]:
                return self.PAGE
            raise OSError("down")

        g = GoogleRate(fetch=fetch, ttl=300, clock=clock)
        self.assertEqual(g.usd_rub(), 81.5)
        state["ok"] = False
        clock.t = 400
        self.assertEqual(g.usd_rub(), 81.5)  # устаревшее значение лучше, чем ничего
        clock.t = 4000  # старше часа - не показываем
        self.assertIsNone(g.usd_rub())

    def test_unparseable_page_returns_none(self):
        g = GoogleRate(fetch=lambda: "<html></html>", ttl=300, clock=FakeClock())
        self.assertIsNone(g.usd_rub())


if __name__ == "__main__":
    unittest.main()
