"""Для бесплатного Render: адрес /health и самопинг, чтобы сервис не засыпал без входящих запросов."""
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PING_INTERVAL = 600  # Render усыпляет бесплатный сервис после 15 минут без входящих запросов


class _Handler(BaseHTTPRequestHandler):
    def _reply(self, send_body):
        if self.path.split("?")[0] in ("/", "/health"):
            status, body = 200, b"ok"
        else:
            status, body = 404, b"not found"
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def do_GET(self):
        self._reply(True)

    def do_HEAD(self):
        self._reply(False)

    def log_message(self, *args):
        pass


def start_health_server(port, host="0.0.0.0"):
    server = ThreadingHTTPServer((host, port), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def ping_url(base_url):
    """Адрес для самопинга; только https, иначе None."""
    base = (base_url or "").strip()
    if not base.startswith("https://"):
        return None
    return base.rstrip("/") + "/health"


def _open(url):
    with urllib.request.urlopen(url, timeout=15) as resp:  # url из ping_url: только https
        resp.read()


def ping_once(url, opener=None):
    try:
        (opener or _open)(url)
        return True
    except Exception:  # пинг ни при каких условиях не должен ронять бота
        return False


def ping_loop(url, interval, stop, opener=None):
    while not stop.is_set():
        ping_once(url, opener)
        if stop.wait(interval):
            break


def start_self_ping(base_url, interval=PING_INTERVAL):
    url = ping_url(base_url)
    if not url:
        return None
    stop = threading.Event()
    threading.Thread(target=ping_loop, args=(url, interval, stop), daemon=True).start()
    return stop
