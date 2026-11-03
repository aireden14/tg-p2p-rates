import io
import unittest
import urllib.error
from unittest import mock

from p2p_rates import bybit
from p2p_rates.bybit import BybitError


def http_error(code, body=b""):
    return urllib.error.HTTPError("https://api2.bybit.com/x", code, "msg", {}, io.BytesIO(body))


class HttpErrorMessageTests(unittest.TestCase):
    def test_status_code_in_message(self):
        with mock.patch("urllib.request.urlopen", side_effect=http_error(403)):
            with self.assertRaises(BybitError) as ctx:
                bybit._http_post({})
        self.assertIn("HTTP 403", str(ctx.exception))

    def test_body_snippet_in_message(self):
        body = b"The request could not be satisfied. Geo block " + b"x" * 500
        with mock.patch("urllib.request.urlopen", side_effect=http_error(403, body)):
            with self.assertRaises(BybitError) as ctx:
                bybit._http_post({})
        message = str(ctx.exception)
        self.assertIn("Geo block", message)
        self.assertLess(len(message), 250)

    def test_network_error_still_reported(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("dns")):
            with self.assertRaises(BybitError) as ctx:
                bybit._http_post({})
        self.assertIn("URLError", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
