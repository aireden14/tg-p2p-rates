"""Ссылка под подписью «Bybit P2P»: реферальная (если задана) или обычная страница P2P."""
import os

# ВРЕМЕННАЯ ссылка: у владельца бота своей реферальной ссылки нет, 04.11.2026 по его просьбе («любую, потом поменяю»)
# взята партнёрская ссылка Bybit с кодом 50394, найденная в интернете. Код принадлежит стороннему партнёру, не владельцу
# бота. Свою ссылку (Bybit → Referral Program) задать переменной BYBIT_REF_URL (на Render: Environment) или заменить здесь.
DEFAULT_REF_URL = "https://partner.bybit.com/b/50394"
MAX_LEN = 300
_FORBIDDEN = set("\"'<>`\\ \t\r\n")


def safe_url(url):
    """Только https, без пробелов, кавычек и скобок: ссылка попадает в HTML сообщения."""
    if not isinstance(url, str):
        return None
    value = url.strip()
    if not value.startswith("https://") or len(value) > MAX_LEN or any(c in _FORBIDDEN for c in value):
        return None
    return value


def load_ref_url(env=None):
    env = os.environ if env is None else env
    return safe_url(env.get("BYBIT_REF_URL")) or DEFAULT_REF_URL
