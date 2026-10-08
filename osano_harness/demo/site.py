# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Local demo site that imitates a CMS marketing home page and an MVC loan-application step.

Two variants, switched at runtime (/__variant?set=before|after), on two environments (/prod, /lle):

before  typical first-pass Osano setup: Permissive mode, GTM above Osano, no consent default,
        Meta pixel / Hotjar / YouTube hard-coded (bypass consent), an unknown Heap script,
        the prod apply page loading the LLE config (and LLE loading prod), Consent Mode v1 only.
after   the fix: Osano first, Strict mode, Consent Mode v2 default, every tag gated — but Google Maps
        was classified MARKETING, so address autocomplete dies when marketing is refused (regression),
        and LLE gained a new unclassified chat widget.
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

CUSTOMER = "DemoCustomer"
CONFIG = {"prod": "demo-prod-config", "lle": "demo-lle-config"}
STATE = {"variant": "before"}


def _osano(env_cfg: str, mode: str, honor_gpc: bool) -> str:
    return (f"<script>window.__DEMO_CMP={{mode:'{mode}',consentModel:'opt-in',honorGpc:{str(honor_gpc).lower()}}};"
            f"</script>\n<script src=\"https://cmp.osano.com/{CUSTOMER}/{env_cfg}/osano.js\"></script>")


GTAG_V2_DEFAULT = ("<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
                   "gtag('consent','default',{ad_storage:'denied',analytics_storage:'denied',"
                   "ad_user_data:'denied',ad_personalization:'denied',wait_for_update:500});</script>")
GTAG_V1_DEFAULT = ("<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
                   "gtag('consent','default',{ad_storage:'denied',analytics_storage:'denied'});</script>")
GTAG_NO_DEFAULT = "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}</script>"
GTAG_LOAD = ("<script async src=\"https://www.googletagmanager.com/gtag/js?id=G-DEMO123\"></script>\n"
             "<script>gtag('js', new Date()); gtag('config','G-DEMO123');</script>")


def gated(src: str, category: str) -> str:
    return f'<script type="text/plain" data-oth-category="{category}" data-src="{src}"></script>'


def plain(src: str) -> str:
    return f'<script async src="{src}"></script>'


FB = "https://connect.facebook.net/en_US/fbevents.js"
BING = "https://bat.bing.com/bat.js"
CLARITY = "https://www.clarity.ms/tag/demo"
HOTJAR = "https://static.hotjar.com/c/hotjar-123.js?sv=6"
HEAP = "https://cdn.heapanalytics.com/js/heap-123.js"
CHAT = "https://widget.newchat-vendor.io/loader.js"
MAPS = "https://maps.googleapis.com/maps/api/js?libraries=places&key=DEMO"
YT = "https://www.youtube.com/embed/demo123"

STYLE = ("<style>body{font:16px/1.5 Segoe UI,sans-serif;margin:0;color:#14202e}header{background:#c8102e;color:#fff;"
         "padding:14px 24px;font-weight:700}main{padding:24px;max-width:900px}label{display:block;margin:10px 0 4px}"
         "input{padding:8px;width:320px}button.cta{background:#c8102e;color:#fff;border:0;padding:10px 18px;"
         "border-radius:4px}</style>")


def home(env: str, variant: str) -> str:
    cfg = CONFIG[env]
    if variant == "before":
        head = "\n".join([GTAG_NO_DEFAULT, GTAG_LOAD, _osano(cfg, "permissive", False),
                          plain(FB), gated(BING, "MARKETING"), gated(CLARITY, "ANALYTICS"), plain(HOTJAR), plain(HEAP)])
        video = f'<iframe width="480" height="270" src="{YT}" title="video"></iframe>'
    else:
        head = "\n".join([_osano(cfg, "strict", True), GTAG_V2_DEFAULT, GTAG_LOAD, gated(FB, "MARKETING"),
                          gated(BING, "MARKETING"), gated(CLARITY, "ANALYTICS"), gated(HOTJAR, "ANALYTICS")]
                         + ([plain(CHAT)] if env == "lle" else []))
        video = (f'<iframe width="480" height="270" data-oth-category="MARKETING" data-oth-src="{YT}" '
                 f'title="video"></iframe>')
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>DEMO Cash — Home ({env})</title>{head}{STYLE}"
            f"</head><body><header>DEMO Cash Express — marketing site ({env.upper()}, {variant})</header><main>"
            f"<h1>Fast cash, fair terms</h1><p>Sample CMS marketing page used by the Osano test harness.</p>"
            f"<p><a id='apply-link' href='/{env}/payday-lending/payday-loans/step/one'>Apply now</a></p>"
            f"{video}</main></body></html>")


def apply_step_one(env: str, variant: str) -> str:
    if variant == "before":
        wrong_cfg = CONFIG["lle" if env == "prod" else "prod"]   # copy-paste of the other property's tag
        head = "\n".join([_osano(wrong_cfg, "permissive", False), GTAG_V1_DEFAULT, GTAG_LOAD,
                          plain(BING), gated(FB, "MARKETING"), plain(MAPS)])
    else:
        head = "\n".join([_osano(CONFIG[env], "strict", True), GTAG_V2_DEFAULT, GTAG_LOAD,
                          gated(BING, "MARKETING"), gated(FB, "MARKETING"), gated(MAPS, "MARKETING")])
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>DEMO Cash — Apply step 1 ({env})</title>"
            f"{head}{STYLE}</head><body><header>DEMO Cash Express — apply ({env.upper()}, {variant})</header><main>"
            f"<h1>Payday loan application — step 1</h1>"
            f"<form id='apply-step-one' method='post' action='#' onsubmit='return false'>"
            f"<input type='hidden' name='__RequestVerificationToken' value='demo'>"
            f"<label for='zip'>ZIP code</label><input id='zip' name='zip' autocomplete='postal-code'>"
            f"<label for='addr'>Street address</label><input id='addr' name='addr'>"
            f"<p><button class='cta' id='continue' type='submit'>Continue</button></p></form></main></body></html>")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the console quiet
        pass

    def _send(self, code: int, body: str = "", ctype: str = "text/html; charset=utf-8", cookies=()):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for c in cookies:
            self.send_header("Set-Cookie", c)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        parts = urlsplit(self.path)
        path = parts.path.rstrip("/") or "/"
        if path == "/__variant":
            v = parse_qs(parts.query).get("set", [""])[0]
            if v in ("before", "after"):
                STATE["variant"] = v
            return self._send(200, STATE["variant"], "text/plain")
        env = path.split("/")[1] if path.count("/") >= 1 else ""
        if env in CONFIG and path in (f"/{env}",):
            return self._send(200, home(env, STATE["variant"]))
        if env in CONFIG and path == f"/{env}/payday-lending/payday-loans/step/one":
            return self._send(200, apply_step_one(env, STATE["variant"]), cookies=(
                "ASP.NET_SessionId=demo; path=/; HttpOnly; SameSite=Lax",
                "__RequestVerificationToken_demo=demo; path=/; HttpOnly; SameSite=Strict"))
        if path == "/":
            return self._send(200, "<p>Demo site: <a href='/prod/'>/prod/</a> · <a href='/lle/'>/lle/</a></p>")
        return self._send(404, "not found", "text/plain")


class _ExclusiveServer(ThreadingHTTPServer):
    """Refuse a port another process holds. On Windows SO_REUSEADDR lets two servers share a port,
    so requests would split between a 'before' and an 'after' demo silently."""
    allow_reuse_address = False

    def server_bind(self):
        import socket
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class DemoServer:
    """with DemoServer(port) as srv: srv.set_variant('after')"""

    def __init__(self, port: int = 8770):
        self.httpd = _ExclusiveServer(("127.0.0.1", port), _Handler)
        self.port = port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()

    @staticmethod
    def set_variant(name: str) -> None:
        if name not in ("before", "after"):
            raise ValueError(name)
        STATE["variant"] = name
