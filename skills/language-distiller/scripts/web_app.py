"""The installable web version of a course app (build_course_app.py --web DIR).

The single-file app carries its sound inside the page. The web version is a folder for a web host: the page without
the sound (index.html), one text file per sound block (audio/au-<block>.<hash>.txt, the same "id:base64;…" text the
page would carry, named by its content so an update only fetches what changed), a web app manifest and icons (Chrome
offers "Install app"), and a service worker (sw.js) that keeps the whole course on the phone for offline use and
fetches a new version in the background; the app then shows "Neue Version bereit – Aktualisieren".

Hosting: any HTTPS host serves it. The folder also carries _headers (Cloudflare Pages: cache rules, noindex) and
robots.txt, and a 404.html: without one, Cloudflare Pages answers every unknown address with index.html, which would
show the app through any path left open. Pages also redirects /index.html to / and /login.html to /login, so the
service worker keeps the page as "./" and leaves both login addresses to the host. A login in front of the host (Cloudflare Access) keeps a private course
private; login.html is the one page the service worker never answers, so opening it reaches the host's login when a
session has expired.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct
import zlib

COLOURS = {"bg": "#17191f", "accent": "#b19ac8", "ink": "#ebe9e4"}    # the sheets' theme
MAX_FILE = 25 * 1024 * 1024                                             # Cloudflare Pages' limit for one file

# ---------------------------------------------------------------- the icon: a speech bubble, drawn without a library
def _rgb(colour):
    return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))


def _round_rect(px, py, cx, cy, hw, hh, r):
    qx, qy = abs(px - cx) - (hw - r), abs(py - cy) - (hh - r)
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r


def _triangle(px, py, a, b, c):
    """Signed distance to a triangle (negative inside)."""
    e = [(b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1]), (a[0] - c[0], a[1] - c[1])]
    v = [(px - a[0], py - a[1]), (px - b[0], py - b[1]), (px - c[0], py - c[1])]
    s = 1.0 if e[0][0] * e[2][1] - e[0][1] * e[2][0] > 0 else -1.0
    best, side = float("inf"), float("inf")
    for (ex, ey), (vx, vy) in zip(e, v):
        t = max(0.0, min(1.0, (vx * ex + vy * ey) / (ex * ex + ey * ey)))
        dx, dy = vx - ex * t, vy - ey * t
        best = min(best, dx * dx + dy * dy)
        side = min(side, s * (vx * ey - vy * ex))
    return -math.sqrt(best) * (1.0 if side > 0 else -1.0)


def _png(size, rows):
    raw = b"".join(b"\x00" + bytes(row) for row in rows)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def icon_png(size, maskable=False, colours=COLOURS):
    """A speech bubble with three dots on the app's dark background. maskable: full bleed, the bubble inside the
    middle 80 % (Android cuts the icon to its own shape); otherwise a rounded square with transparent corners."""
    bg, accent = _rgb(colours["bg"]), _rgb(colours["accent"])
    k = size / 512 * (0.78 if maskable else 1.0)                          # the bubble's scale
    c = size / 2
    rect = (c, c - 26 * k, 168 * k, 118 * k, 56 * k)                      # centre x, y, half width, half height, corner
    tail = ((c - 92 * k, c + 60 * k), (c - 118 * k, c + 150 * k), (c - 20 * k, c + 84 * k))
    dots = [(c + dx * k, c - 26 * k, 25 * k) for dx in (-70, 0, 70)]
    box = (c - 175 * k, c - 150 * k, c + 175 * k, c + 156 * k)            # where the bubble can be
    corner = size * 0.22
    rows = []
    for y in range(size):
        py = y + 0.5
        row = bytearray()
        for x in range(size):
            px = x + 0.5
            alpha = 1.0 if maskable else min(1.0, max(0.0, 0.5 - _round_rect(px, py, c, c, c, c, corner)))
            r, g, b = bg
            if box[0] <= px <= box[2] and box[1] <= py <= box[3]:
                d = min(_round_rect(px, py, *rect), _triangle(px, py, *tail))
                cover = min(1.0, max(0.0, 0.5 - d))
                if cover:
                    r, g, b = (round(bg[i] + (accent[i] - bg[i]) * cover) for i in range(3))
                    dot = min(math.hypot(px - dx, py - dy) - rad for dx, dy, rad in dots)
                    inner = min(1.0, max(0.0, 0.5 - dot))
                    if inner:
                        r, g, b = (round(v + (bg[i] - v) * inner) for i, v in enumerate((r, g, b)))
            row += bytes((r, g, b, round(255 * alpha)))
        rows.append(row)
    return _png(size, rows)


# ---------------------------------------------------------------- the page's part: offline copy and updates
WEB_CSS = """
  .web-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:8px 0 2px;padding:8px 12px;border:1px solid var(--accent);
    border-radius:12px;background:#24272e;font-size:15px;line-height:1.4}
  .web-bar[hidden]{display:none}
  .web-bar span{flex:1 1 180px}
  .web-bar button{font:inherit;font-weight:800;min-height:40px;padding:6px 16px;border-radius:10px;border:0;cursor:pointer;
    background:var(--accent);color:#1a1030}
"""
WEB_BAR = '<div class="web-bar" id="web-bar" role="status" hidden><span id="web-msg"></span><button type="button" id="web-go" hidden></button></div>\n'
WEB_SETTINGS = ('<div class="backup"><button type="button" id="upd-btn">Nach Updates suchen</button></div>'
                '<p class="stat" id="upd-stat"></p>')

WEB_JS = """
  /* ---------------- the web version: the whole course kept for offline use, and updates (WEB is null in the single file) ---------------- */
  if(WEB&&'serviceWorker' in navigator) (function(){
    var sw=navigator.serviceWorker, bar=d.getElementById('web-bar'), msg=d.getElementById('web-msg'), go=d.getElementById('web-go'),
        stat=d.getElementById('upd-stat'), btn=d.getElementById('upd-btn'), reg=null, act=null, had=!!sw.controller, last=Date.now(), reloading=false;
    function show(text,label,fn){ msg.textContent=text||''; go.hidden=!label; act=label?fn:null; if(label) go.textContent=label; bar.hidden=!text; }
    go.addEventListener('click',function(){ if(act) act(); });
    function ready(w){ show('Neue Version bereit.','Aktualisieren',function(){ show('Wird aktualisiert …'); w.postMessage('skip'); }); }
    function watch(w){ if(w) w.addEventListener('statechange',function(){ if(w.state==='installed'&&sw.controller) ready(w); }); }
    function login(){ show('Für Updates bitte einmal anmelden.','Anmelden',function(){ location.href='login.html'; }); }
    sw.addEventListener('controllerchange',function(){ if(had&&!reloading){ reloading=true; location.reload(); } had=true; });
    sw.addEventListener('message',function(e){ var m=e.data||{};
      if(m.t==='progress'&&!sw.controller) show('Wird für offline gespeichert … '+Math.floor(100*m.done/m.total)+' %');
      if(m.t==='fail'&&!sw.controller) show(m.quota?'Nicht genug Speicherplatz auf dem Handy.':'Das Speichern wurde unterbrochen.',
        m.quota?'':'Erneut versuchen',function(){ location.reload(); });          /* a retry resumes where it stopped */
      if(m.t==='done'&&!had){ show('Offline bereit ✓'); setTimeout(function(){ if(msg.textContent==='Offline bereit ✓') show(''); },5000); } });
    sw.register('sw.js',{updateViaCache:'none'}).then(function(r){ reg=r;
      if(r.waiting&&sw.controller) ready(r.waiting); watch(r.installing);
      r.addEventListener('updatefound',function(){ watch(r.installing); }); },function(){});
    function why(){ return fetch('sw.js',{cache:'no-store',redirect:'manual'}).then(function(r){ return r.type==='opaqueredirect'?'login':r.ok?'ok':'down'; },function(){ return 'offline'; }); }
    function check(manual){ if(!reg) return; last=Date.now(); if(manual&&stat) stat.textContent='Suche …';
      reg.update().then(function(){ if(manual&&stat) setTimeout(function(){ stat.textContent=reg.installing||reg.waiting?'Neue Version wird geladen …':'Du hast die neueste Version.'; },1500); },
        function(){ why().then(function(w){ if(w==='login') login();
          if(manual&&stat) stat.textContent=w==='login'?'Bitte einmal anmelden (oben).':w==='offline'?'Kein Internet. Später nochmal.':'Gerade nicht erreichbar. Später nochmal.'; }); }); }
    if(btn) btn.addEventListener('click',function(){ check(true); });
    d.addEventListener('visibilitychange',function(){ if(!d.hidden&&Date.now()-last>30*60000) check(false); });
    setInterval(function(){ if(!d.hidden) check(false); },60*60000);
    if(navigator.storage&&navigator.storage.persisted) navigator.storage.persisted().then(function(p){ if(!p) return navigator.storage.persist(); }).catch(function(){});
  })();
"""

# ---------------------------------------------------------------- the service worker
SW_JS = """'use strict';
/* the course for offline use: every file of this version in one cache; an update is a new version (a new list),
   fetched in the background; files named by their content come from the old cache, the rest from the host */
var VERSION='__VERSION__', PREFIX='__PREFIX__', FILES=__FILES__, CACHE=PREFIX+VERSION;
function abs(f){ return new URL(f,self.registration.scope).href; }
function tell(m){ return self.clients.matchAll({includeUncontrolled:true}).then(function(cs){ cs.forEach(function(c){ c.postMessage(m); }); }); }
function mine(n){ return n!==CACHE&&n.indexOf(PREFIX)===0; }
self.addEventListener('install',function(e){ e.waitUntil((async function(){ try{
  var cache=await caches.open(CACHE), old=(await caches.keys()).filter(mine), done=0;
  for(var i=0;i<FILES.length;i++){ var f=FILES[i], url=abs(f), hit=null;
    if(!(await cache.match(url))){                                    /* not there yet (an install can resume) */
      if(/\\.[0-9a-f]{12}\\./.test(f)) for(var j=0;j<old.length&&!hit;j++) hit=await (await caches.open(old[j])).match(url);
      if(!hit){ hit=await fetch(url,{cache:'reload',credentials:'same-origin',redirect:'manual'});
        if(!hit.ok||hit.type==='opaqueredirect') throw new Error(f+': '+(hit.status||'login')); }
      await cache.put(url,hit); }
    done++;
    if(done%4===0||done===FILES.length) await tell({t:'progress',done:done,total:FILES.length}); }
  await tell({t:'done'}); }catch(err){ await tell({t:'fail',quota:!!err&&err.name==='QuotaExceededError'}); throw err; } })()); });
self.addEventListener('activate',function(e){ e.waitUntil(caches.keys().then(function(ns){ return Promise.all(ns.filter(mine).map(function(n){ return caches.delete(n); })); })
  .then(function(){ return self.clients.claim(); })); });
self.addEventListener('message',function(e){ if(e.data==='skip') self.skipWaiting(); });
self.addEventListener('fetch',function(e){ var q=e.request, u=new URL(q.url);
  if(q.method!=='GET'||u.origin!==location.origin||/\\/(login(\\.html)?|sw\\.js)$/.test(u.pathname)) return;
  e.respondWith(caches.open(CACHE).then(function(c){ return c.match(q.mode==='navigate'?abs('./'):u.href,{ignoreSearch:true}); })
    .then(function(hit){ return hit||fetch(q); })); });
"""

LOGIN_HTML = """<!DOCTYPE html>
<html lang="__LANG__"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title><style>body{font:18px/1.5 -apple-system,"Segoe UI",Roboto,sans-serif;background:__BG__;color:__INK__;
display:flex;min-height:90vh;align-items:center;justify-content:center;text-align:center}a{color:__ACCENT__;font-weight:800}</style>
</head><body><p>Angemeldet ✓<br><a href="./">Zurück zur App</a></p>
<script>setTimeout(function(){ location.replace('./'); },1200);</script></body></html>
"""

NOT_FOUND_HTML = """<!DOCTYPE html>
<html lang="__LANG__"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow"><title>404</title></head><body><p>404</p></body></html>
"""

HEADERS = """/*
  X-Robots-Tag: noindex, nofollow
  X-Content-Type-Options: nosniff
/audio/*
  Cache-Control: public, max-age=31536000, immutable
/sw.js
  Cache-Control: no-cache
/
  Cache-Control: no-cache
/manifest.webmanifest
  Cache-Control: no-cache
"""


def head_links(colours=COLOURS):
    """For the page's <head>: the manifest (sent with the login cookie, which a private host needs), colours, icon."""
    return (f'<link rel="manifest" href="manifest.webmanifest" crossorigin="use-credentials">'
            f'<meta name="theme-color" content="{colours["bg"]}"><link rel="icon" href="icons/icon-192.png">'
            f'<link rel="apple-touch-icon" href="icons/icon-192.png">')


def block_name(number, text):
    return f"audio/au-{number}.{hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]}.txt"


def write_site(folder, page, blocks, *, title, lang, key, colours=COLOURS):
    """Write the web app into a new folder. page: the app's HTML without its sound; blocks: {block number: (file name,
    text)} as named by block_name. Returns {"files", "bytes", "too_big", "version"}."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    files = {"index.html": page.encode("utf-8")}
    for name, text in blocks.values():
        files[name] = text.encode("utf-8")
    manifest = {"name": title, "short_name": title if len(title) <= 12 else title[:12].rstrip(), "lang": lang,
                "start_url": "./", "scope": "./", "display": "standalone", "orientation": "portrait",
                "background_color": colours["bg"], "theme_color": colours["bg"],
                "icons": [{"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                          {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                          {"src": "icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}
    files["manifest.webmanifest"] = (json.dumps(manifest, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    files["icons/icon-192.png"] = icon_png(192, colours=colours)
    files["icons/icon-512.png"] = icon_png(512, colours=colours)
    files["icons/maskable-512.png"] = icon_png(512, maskable=True, colours=colours)
    cached = sorted(files, key=lambda name: (name != "index.html", name))   # what the service worker keeps
    version = hashlib.sha256("".join(f"{name}:{hashlib.sha256(files[name]).hexdigest()};" for name in cached)
                             .encode("utf-8")).hexdigest()[:12]
    urls = ["./" if name == "index.html" else name for name in cached]   # the page as its folder: hosts like Cloudflare
    files["sw.js"] = (SW_JS.replace("__VERSION__", version).replace("__PREFIX__", f"{key}:")  # Pages redirect /index.html
                      .replace("__FILES__", json.dumps(urls))).encode("utf-8")
    files["login.html"] = (LOGIN_HTML.replace("__LANG__", lang).replace("__TITLE__", title).replace("__BG__", colours["bg"])
                           .replace("__INK__", colours["ink"]).replace("__ACCENT__", colours["accent"])).encode("utf-8")
    files["404.html"] = NOT_FOUND_HTML.replace("__LANG__", lang).encode("utf-8")   # never the app for an unknown address
    files["_headers"] = HEADERS.encode("utf-8")
    files["robots.txt"] = b"User-agent: *\nDisallow: /\n"
    for name, data in files.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return {"files": len(files), "bytes": sum(len(data) for data in files.values()), "version": version,
            "too_big": sorted(name for name, data in files.items() if len(data) > MAX_FILE)}
