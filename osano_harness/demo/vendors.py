# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Answers every non-local request in demo mode with a stub, so nothing leaves the machine."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from ..catalog import host_matches

HERE = Path(__file__).resolve().parent
_LOCAL = ("127.0.0.1", "localhost")


def _cookie_js(name: str, ping: str, extra: str = "") -> str:
    return (f"(function(){{document.cookie='{name}='+Date.now()+'; path=/; max-age=31536000; SameSite=Lax';"
            f"new Image().src='{ping}';{extra}}})();")


STUBS: list[tuple[str, str, str]] = [
    # (host, content-type, body)
    ("cmp.osano.com", "application/javascript", (HERE / "cmp_stub.js").read_text(encoding="utf-8")),
    ("googletagmanager.com", "application/javascript", (HERE / "gtag_stub.js").read_text(encoding="utf-8")),
    ("connect.facebook.net", "application/javascript",
     _cookie_js("_fbp", "https://www.facebook.com/tr?id=DEMO&ev=PageView", "window.fbq=function(){};")),
    ("bat.bing.com", "application/javascript",
     _cookie_js("_uetsid", "https://bat.bing.com/action/0?ti=DEMO&evt=pageLoad")),
    ("clarity.ms", "application/javascript", _cookie_js("_clck", "https://c.clarity.ms/c.gif?demo=1")),
    ("static.hotjar.com", "application/javascript",
     _cookie_js("_hjSessionUser_123", "https://in.hotjar.com/api/v2/client/sites/123/visit-data",
                "try{localStorage.setItem('_hjid','demo')}catch(e){}")),
    ("cdn.heapanalytics.com", "application/javascript",
     _cookie_js("_hp2_id.123", "https://heapanalytics.com/h?a=123")),
    ("widget.newchat-vendor.io", "application/javascript",
     _cookie_js("nc_visitor", "https://api.newchat-vendor.io/v1/ping")),
    ("maps.googleapis.com", "application/javascript",
     "window.google=window.google||{};window.google.maps={places:{Autocomplete:function(){}}};"),
    ("youtube.com", "text/html",
     "<!doctype html><title>video</title><body style='margin:0;background:#000;color:#fff;font:14px sans-serif'>"
     "demo video player</body>"),
]


def route_handler(route) -> None:
    url = route.request.url
    host = (urlsplit(url).hostname or "").lower()
    if host in _LOCAL:
        route.continue_()
        return
    for stub_host, ctype, body in STUBS:
        if host_matches(host, stub_host):
            route.fulfill(status=200, content_type=ctype, body=body,
                          headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-store"})
            return
    # Pixels, beacons and anything else: empty answer.
    route.fulfill(status=204, body="")
