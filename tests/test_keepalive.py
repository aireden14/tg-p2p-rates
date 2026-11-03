import threading
import unittest
import urllib.error
import urllib.request

from p2p_rates import keepalive


def get(url, method="GET"):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, resp.read().decode()


class HealthServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = keepalive.start_health_server(0, host="127.0.0.1")
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_health_ok(self):
        self.assertEqual(get(self.base + "/health"), (200, "ok"))

    def test_root_ok(self):
        self.assertEqual(get(self.base + "/")[0], 200)

    def test_head_ok(self):
        status, body = get(self.base + "/health", method="HEAD")
        self.assertEqual((status, body), (200, ""))

    def test_unknown_path_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            get(self.base + "/admin")
        self.assertEqual(ctx.exception.code, 404)


class SelfPingTests(unittest.TestCase):
    def test_ping_once_success(self):
        seen = []
        self.assertTrue(keepalive.ping_once("https://x.example/health", opener=seen.append))
        self.assertEqual(seen, ["https://x.example/health"])

    def test_ping_once_swallows_errors(self):
        def boom(url):
            raise OSError("down")

        self.assertFalse(keepalive.ping_once("https://x.example/health", opener=boom))

    def test_ping_url_only_https(self):
        self.assertEqual(keepalive.ping_url("https://bot.onrender.com"), "https://bot.onrender.com/health")
        self.assertEqual(keepalive.ping_url("https://bot.onrender.com/"), "https://bot.onrender.com/health")
        self.assertIsNone(keepalive.ping_url("file:///etc/passwd"))
        self.assertIsNone(keepalive.ping_url("http://insecure.example"))
        self.assertIsNone(keepalive.ping_url(""))

    def test_loop_pings_until_stopped(self):
        stop = threading.Event()
        calls = []

        def opener(url):
            calls.append(url)
            if len(calls) >= 3:
                stop.set()

        keepalive.ping_loop("https://x.example/health", interval=0.01, stop=stop, opener=opener)
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()
