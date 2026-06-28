"""Browser interface mirroring the PiTFT controls.

The Tk app remains the single source of truth: this server only *reads* a
snapshot of its state and *schedules* actions (cast / refresh) back onto the Tk
main loop, so the physical screen and the web page never disagree.

Implemented with the standard library only (no extra dependencies), matching the
HLS server already used by the cast controller.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional, Protocol


class WebControllable(Protocol):
    """The slice of FullscreenApp the web interface depends on."""

    def get_web_snapshot(self) -> dict: ...

    def web_request_cast(self, uuid: str) -> bool: ...

    def web_request_refresh(self) -> None: ...


def _make_handler(app: WebControllable):
    class _Handler(BaseHTTPRequestHandler):
        # Silence per-request stderr logging — keeps the boot console clean.
        def log_message(self, *_args) -> None:  # noqa: D401
            return

        def _send_json(self, payload: dict, status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html: str) -> None:
            self._send_text(html, "text/html; charset=utf-8")

        def _send_text(
            self,
            text: str,
            content_type: str,
            cache: str = "no-cache",
            extra_headers: Optional[dict] = None,
        ) -> None:
            body = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            for key, value in (extra_headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> dict:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
                return data if isinstance(data, dict) else {}
            except (ValueError, UnicodeDecodeError):
                return {}

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/index.html"):
                self._send_html(INDEX_HTML)
                return
            if self.path == "/api/state":
                self._send_json(app.get_web_snapshot())
                return
            if self.path == "/manifest.webmanifest":
                self._send_text(
                    MANIFEST_JSON,
                    "application/manifest+json",
                    cache="max-age=86400",
                )
                return
            if self.path == "/sw.js":
                # Allow the worker to control the whole origin from /sw.js.
                self._send_text(
                    SERVICE_WORKER_JS,
                    "text/javascript",
                    cache="no-cache",
                    extra_headers={"Service-Worker-Allowed": "/"},
                )
                return
            if self.path in ("/icon.svg", "/apple-touch-icon.png"):
                # apple-touch-icon also points here; iOS accepts the inline SVG.
                self._send_text(ICON_SVG, "image/svg+xml", cache="max-age=86400")
                return
            if self.path == "/icon-maskable.svg":
                self._send_text(
                    ICON_MASKABLE_SVG, "image/svg+xml", cache="max-age=86400"
                )
                return
            self._send_json({"error": "not found"}, status=404)

        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/api/refresh":
                app.web_request_refresh()
                self._send_json({"ok": True})
                return
            if self.path == "/api/cast":
                uuid = str(self._read_json_body().get("uuid", "")).strip()
                if not uuid:
                    self._send_json({"ok": False, "error": "missing uuid"}, status=400)
                    return
                ok = app.web_request_cast(uuid)
                self._send_json({"ok": ok}, status=200 if ok else 404)
                return
            self._send_json({"error": "not found"}, status=404)

    return _Handler


class WebInterface:
    """Runs the browser UI server in a background thread."""

    def __init__(self, app: WebControllable, host: str = "0.0.0.0", port: int = 8080) -> None:
        self.app = app
        self.host = host
        self.port = port
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        handler = _make_handler(self.app)
        self._server = ThreadingHTTPServer((self.host, self.port), handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="vinyl-web",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        self._server = None
        self._thread = None


# --- Browser UI -----------------------------------------------------------
# Single self-contained page; palette mirrors src/display/material_widgets.py.
# Polls /api/state for the speaker list + status + live audio level, and POSTs
# to /api/cast and /api/refresh — the same actions as tapping the screen.
INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="theme-color" content="#12161f" />
<title>Pi Audio Cast</title>
<link rel="manifest" href="/manifest.webmanifest" />
<link rel="icon" type="image/svg+xml" href="/icon.svg" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
<meta name="mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
<meta name="apple-mobile-web-app-title" content="Audio Cast" />
<style>
  :root {
    --panel:#12161f; --surface:#1a2030; --surface-high:#232a3a;
    --on:#eef2f8; --on-var:#9aa6b8; --primary:#3d8f62; --primary-c:#2d6b4a;
    --on-primary:#fff; --success:#6ecf94; --error:#e07b7b; --outline:#3d4658;
  }
  * { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
  html,body { margin:0; height:100%; }
  body {
    background:#0a0c12; color:var(--on);
    font-family:"Roboto","Inter","Segoe UI",system-ui,Arial,sans-serif;
    display:flex; flex-direction:column; min-height:100vh;
  }
  header {
    display:flex; align-items:center; gap:10px;
    padding:14px 16px; background:var(--panel);
    border-bottom:1px solid var(--outline); position:sticky; top:0; z-index:5;
  }
  #status {
    flex:1; font-weight:700; font-size:15px; color:var(--on-var);
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  }
  #status.success { color:var(--success); }
  #status.error { color:var(--error); }
  button.icon {
    border:none; cursor:pointer; border-radius:50%;
    width:40px; height:40px; font-size:18px; line-height:1;
    background:var(--surface); color:var(--on-var);
  }
  button.icon:active { background:var(--primary-c); color:#fff; }
  #refresh.spinning { animation:spin 0.8s linear infinite; }
  @keyframes spin { to { transform:rotate(360deg); } }
  main {
    flex:1; display:flex; gap:12px; padding:12px;
    max-width:760px; width:100%; margin:0 auto;
  }
  #speakers { flex:1; display:flex; flex-direction:column; gap:8px; min-width:0; }
  .speaker {
    display:flex; align-items:center; justify-content:space-between; gap:8px;
    padding:14px 16px; border-radius:14px; cursor:pointer;
    background:var(--surface); border:2px solid transparent;
    color:var(--on); font-size:15px; font-weight:600; text-align:left;
  }
  .speaker:active { background:var(--surface-high); }
  .speaker.active { background:var(--primary); border-color:var(--success); color:#fff; }
  .speaker .tag { font-size:11px; font-weight:700; color:var(--on-var); }
  .speaker.active .tag { color:rgba(255,255,255,.8); }
  .empty { color:var(--on-var); text-align:center; padding:28px 8px; font-weight:600; }
  #viz {
    width:42%; max-width:300px; min-height:220px; border-radius:14px;
    background:linear-gradient(#0a0c12,#141822);
    display:flex; align-items:flex-end; gap:3px; padding:10px;
  }
  .bar { flex:1; min-width:3px; border-radius:2px 2px 0 0; background:#243044; height:2px;
         transition:height .08s linear; }
  @media (max-width:560px) {
    main { flex-direction:column-reverse; }
    #viz { width:100%; min-height:120px; height:120px; }
  }
</style>
</head>
<body>
  <header>
    <div id="status">Connecting…</div>
    <button class="icon" id="refresh" title="Refresh">&#8635;</button>
  </header>
  <main>
    <div id="speakers"><div class="empty">Loading…</div></div>
    <div id="viz"></div>
  </main>
<script>
(function () {
  const statusEl = document.getElementById("status");
  const speakersEl = document.getElementById("speakers");
  const refreshBtn = document.getElementById("refresh");
  const viz = document.getElementById("viz");

  const BAR_COUNT = 28;
  const history = new Array(BAR_COUNT).fill(0);
  const bars = [];
  for (let i = 0; i < BAR_COUNT; i++) {
    const b = document.createElement("div");
    b.className = "bar";
    viz.appendChild(b);
    bars.push(b);
  }
  function barColor(v) {
    if (v < 0.05) return "#141a24";
    if (v < 0.35) return "#1a2433";
    if (v < 0.6) return "#243044";
    if (v < 0.8) return "#2e3d55";
    return "#3a5068";
  }
  function renderBars() {
    const h = viz.clientHeight - 20;
    for (let i = 0; i < BAR_COUNT; i++) {
      const v = history[i];
      bars[i].style.height = Math.max(2, Math.round(h * v)) + "px";
      bars[i].style.background = barColor(v);
    }
  }

  let sig = "";
  function renderSpeakers(targets) {
    const newSig = targets.map(t => t.uuid + ":" + t.active).join("|");
    if (newSig === sig) return;
    sig = newSig;
    speakersEl.innerHTML = "";
    if (!targets.length) {
      const e = document.createElement("div");
      e.className = "empty";
      e.textContent = "No speakers found";
      speakersEl.appendChild(e);
      return;
    }
    for (const t of targets) {
      const el = document.createElement("button");
      el.className = "speaker" + (t.active ? " active" : "");
      const name = document.createElement("span");
      name.textContent = t.name;
      el.appendChild(name);
      if (t.is_group) {
        const tag = document.createElement("span");
        tag.className = "tag";
        tag.textContent = "group";
        el.appendChild(tag);
      }
      el.addEventListener("click", () => cast(t.uuid));
      speakersEl.appendChild(el);
    }
  }

  async function cast(uuid) {
    try {
      await fetch("/api/cast", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uuid }),
      });
    } catch (e) {}
    poll();
  }

  refreshBtn.addEventListener("click", async () => {
    refreshBtn.classList.add("spinning");
    try { await fetch("/api/refresh", { method: "POST" }); } catch (e) {}
    setTimeout(() => refreshBtn.classList.remove("spinning"), 900);
  });

  async function poll() {
    try {
      const res = await fetch("/api/state", { cache: "no-store" });
      const s = await res.json();
      statusEl.textContent = s.status.text;
      statusEl.className = s.status.kind;
      renderSpeakers(s.targets || []);
      history.shift();
      history.push(Math.max(0, Math.min(1, s.level || 0)));
      renderBars();
    } catch (e) {
      statusEl.textContent = "Disconnected";
      statusEl.className = "error";
    }
  }

  poll();
  setInterval(poll, 200);

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    });
  }
})();
</script>
</body>
</html>
"""


# --- PWA assets -----------------------------------------------------------
# These make the page installable to the home screen as a standalone app.

MANIFEST_JSON = json.dumps(
    {
        "name": "Pi Audio Cast",
        "short_name": "Audio Cast",
        "description": "Cast USB audio to Google speakers — remote for the Pi display.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0a0c12",
        "theme_color": "#12161f",
        "icons": [
            {"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
            {
                "src": "/icon-maskable.svg",
                "sizes": "any",
                "type": "image/svg+xml",
                "purpose": "maskable",
            },
        ],
    },
    indent=2,
)


# Cache the app shell so it opens instantly (even briefly offline); API calls
# always go to the network so speaker state is never stale.
SERVICE_WORKER_JS = """const CACHE = "vinyl-cast-v1";
const SHELL = ["/", "/manifest.webmanifest", "/icon.svg", "/icon-maskable.svg"];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) {
    return; // always live: speakers, status, levels, actions
  }
  event.respondWith(
    caches.match(event.request).then((cached) =>
      cached ||
      fetch(event.request).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(event.request, copy)).catch(() => {});
        return res;
      }).catch(() => cached)
    )
  );
});
"""


# Vinyl-record app icon (full-bleed, safe for maskable). Palette matches the UI.
def _icon_svg(record_radius: int) -> str:
    grooves = "".join(
        f'<circle cx="256" cy="256" r="{r}" fill="none" '
        f'stroke="#1a2433" stroke-width="3"/>'
        for r in range(record_radius - 16, 92, -16)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
        '<rect width="512" height="512" fill="#12161f"/>'
        f'<circle cx="256" cy="256" r="{record_radius}" fill="#0a0c12"/>'
        f"{grooves}"
        '<circle cx="256" cy="256" r="78" fill="#3d8f62"/>'
        '<circle cx="256" cy="256" r="76" fill="none" stroke="#6ecf94" stroke-width="3"/>'
        '<circle cx="256" cy="256" r="14" fill="#0a0c12"/>'
        "</svg>"
    )


ICON_SVG = _icon_svg(record_radius=196)
# Maskable variant keeps the record inside the ~80% safe zone (more padding).
ICON_MASKABLE_SVG = _icon_svg(record_radius=168)
