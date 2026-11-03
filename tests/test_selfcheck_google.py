import unittest

from p2p_rates.selfcheck import check_google


class FakeGoogle:
    def __init__(self, value):
        self.value = value

    def usd_rub(self):
        return self.value


class CheckGoogleTests(unittest.TestCase):
    def test_ok(self):
        lines = []
        self.assertTrue(check_google(FakeGoogle(81.4847), lines.append))
        self.assertIn("Google: ok", lines[0])
        self.assertIn("81,48", lines[0])

    def test_unavailable(self):
        lines = []
        self.assertFalse(check_google(FakeGoogle(None), lines.append))
        self.assertIn("Google: недоступен", lines[0])


if __name__ == "__main__":
    unittest.main()
