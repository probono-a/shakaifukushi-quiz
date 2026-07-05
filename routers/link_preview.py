import re
import urllib.request
import urllib.error
from html.parser import HTMLParser
from urllib.parse import urlparse

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api")

# インメモリキャッシュ: url -> metadata dict
_cache: dict[str, dict] = {}


class _OGPParser(HTMLParser):
    """OGP / title メタタグを抽出する軽量パーサー"""

    def __init__(self):
        super().__init__()
        self.title: str = ""
        self.description: str = ""
        self.image: str = ""
        self._in_title = False
        self._done = False

    def handle_starttag(self, tag: str, attrs):
        if self._done:
            return
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            prop = a.get("property", "") or a.get("name", "")
            content = a.get("content", "")
            if prop == "og:title" and not self.title:
                self.title = content
            elif prop in ("og:description", "description") and not self.description:
                self.description = content
            elif prop == "og:image" and not self.image:
                self.image = content
        elif tag == "body":
            self._done = True

    def handle_data(self, data: str):
        if self._in_title and not self.title:
            self.title = data.strip()

    def handle_endtag(self, tag: str):
        if tag == "title":
            self._in_title = False


def _detect_charset(http_ct: str, raw: bytes) -> str:
    """HTTP Content-Type ヘッダと HTML 先頭バイトからエンコーディングを特定する"""
    # 1. HTTP ヘッダ優先
    m = re.search(r"charset=[\"']?([\w-]+)", http_ct)
    if m:
        return m.group(1)
    # 2. HTML 内 <meta charset="..."> または <meta http-equiv="Content-Type" ...>
    snippet = raw[:4096].decode("ascii", errors="replace")
    m = re.search(r'charset=["\']?([\w-]+)', snippet, re.IGNORECASE)
    if m:
        return m.group(1)
    return "utf-8"


def _fetch_metadata(url: str) -> dict:
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    favicon = f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
    base = {"url": url, "domain": domain, "favicon": favicon, "title": "", "description": "", "image": ""}

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "ja,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            ct = resp.headers.get("Content-Type", "")
            if "text/html" not in ct:
                return base
            raw = resp.read(65536)  # 先頭 64KB
            charset = _detect_charset(ct, raw)
            html = raw.decode(charset, errors="replace")
    except Exception:
        return base

    parser = _OGPParser()
    parser.feed(html)

    base["title"] = parser.title[:120] if parser.title else ""
    base["description"] = parser.description[:200] if parser.description else ""
    base["image"] = parser.image or ""
    return base


@router.get("/link-preview")
def link_preview(url: str = Query(..., min_length=5)):
    if not url.startswith(("http://", "https://")):
        return JSONResponse({"error": "invalid url"}, status_code=422)

    if url not in _cache:
        _cache[url] = _fetch_metadata(url)

    return _cache[url]
