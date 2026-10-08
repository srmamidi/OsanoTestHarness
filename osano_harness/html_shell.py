# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Self-contained HTML page shell: tabs, dark/light toggle, read-aloud. No external files.
Everything that came from a website (URLs, cookie names...) goes through esc() — it is untrusted."""
from __future__ import annotations

import html

STATUS_TAG = {"pass": "good", "fail": "danger", "warn": "warn", "error": "info", "na": "muted",
              "improved": "good", "regressed": "danger", "same": "muted", "changed": "info", "n/a": "muted",
              "fixed": "good", "new": "danger", "still": "warn", "gone": "muted", "ok": "muted",
              "added": "info", "removed": "muted", "moved": "info", "recategorised": "warn",
              "IMPROVED": "good", "REGRESSED": "danger", "MIXED": "warn", "UNCHANGED": "muted",
              "high": "danger", "medium": "warn", "low": "info", "info": "muted",
              "ESSENTIAL": "good", "FIRST_PARTY": "good", "ANALYTICS": "info", "MARKETING": "warn",
              "PERSONALIZATION": "info", "OPT-OUT": "warn", "UNCLASSIFIED": "danger",
              "rules": "good", "discovered": "warn", "ignored": "muted", "missing": "danger"}


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def tag(text, kind: str | None = None) -> str:
    k = kind or STATUS_TAG.get(str(text), "muted")
    return f'<span class="tag {k}">{esc(text)}</span>'


def table(headers: list[str], rows: list[list[str]], cls: str = "", empty: str = "Nothing to show.",
          table_id: str = "", row_status: list[str] | None = None) -> str:
    """Cells must already be HTML (use esc()/tag()); a cell may be (html, css_class) for a coloured fill.
    row_status feeds the status filter."""
    if not rows:
        return f'<p class="muted">{esc(empty)}</p>'
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    statuses = row_status or [""] * len(rows)

    def td(c):
        return f'<td class="{c[1]}">{c[0]}</td>' if isinstance(c, tuple) else f"<td>{c}</td>"
    body = "".join(f'<tr data-status="{esc(st)}">' + "".join(td(c) for c in r) + "</tr>"
                   for r, st in zip(rows, statuses))
    tid = f' id="{esc(table_id)}"' if table_id else ""
    return (f'<div class="tbl-wrap"><table{tid} class="{cls}"><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def evidence(items: list[str], _limit: int | None = None) -> str:
    """Every item, never truncated (the reader must not have to click or guess)."""
    if not items:
        return ""
    lis = "".join(f"<li><code>{esc(i)}</code></li>" for i in items)
    return f"<ul class='ev'>{lis}</ul>"


def kpi_cards(cards: list[tuple[str, str, str]]) -> str:
    """(label, value, kind)"""
    return '<div class="cards">' + "".join(
        f'<div class="card {k}"><div class="v">{esc(v)}</div><div class="l">{esc(lab)}</div></div>'
        for lab, v, k in cards) + "</div>"


def bars(groups: list[tuple[str, list[float]]], series: list[str], title: str, width: int = 760) -> str:
    """Horizontal grouped bar chart as inline SVG. groups = [(label, [value per series])]."""
    if not groups:
        return ""
    colors = ["var(--s1)", "var(--s2)", "var(--s3)"]
    vmax = max([max(v) for _, v in groups] + [1])
    row_h = 16 * len(series) + 12
    label_w = 190
    h = row_h * len(groups) + 34
    parts = [f'<svg class="chart" viewBox="0 0 {width} {h}" role="img" aria-label="{esc(title)}">']
    for gi, (label, vals) in enumerate(groups):
        y0 = 8 + gi * row_h
        parts.append(f'<text x="{label_w - 8}" y="{y0 + row_h / 2}" text-anchor="end" class="cl">{esc(label)}</text>')
        for si, v in enumerate(vals):
            w = (width - label_w - 60) * (v / vmax)
            y = y0 + si * 16
            parts.append(f'<rect x="{label_w}" y="{y}" width="{max(w, 1.5):.1f}" height="13" rx="2" fill="{colors[si % 3]}"/>')
            parts.append(f'<text x="{label_w + max(w, 1.5) + 6:.1f}" y="{y + 11}" class="cv">{v:g}</text>')
    lx = label_w
    for si, s in enumerate(series):
        parts.append(f'<rect x="{lx}" y="{h - 16}" width="12" height="12" rx="2" fill="{colors[si % 3]}"/>'
                     f'<text x="{lx + 17}" y="{h - 6}" class="cl">{esc(s)}</text>')
        lx += 30 + 8 * len(s)
    parts.append("</svg>")
    return "".join(parts)


CSS = """
:root{--bg:#0f1217;--panel:#171b22;--border:#2a313c;--text:#e6e9ee;--muted:#9aa4b2;--accent:#5aa9ff;--code-bg:#11151b;
--good:#2fbf71;--good-bg:#12301f;--warn:#e0a32e;--warn-bg:#3a2c10;--danger:#ff6b6b;--danger-bg:#3d1717;--info:#6cb6ff;--info-bg:#132a40;
--muted-bg:#232a33;--s1:#8a96a8;--s2:#5aa9ff;--s3:#2fbf71}
:root[data-theme="light"]{--bg:#f6f7f9;--panel:#ffffff;--border:#d8dde5;--text:#1b2230;--muted:#5b6575;--accent:#0b63c5;--code-bg:#eef1f5;
--good:#13753f;--good-bg:#dcf3e6;--warn:#8a5a00;--warn-bg:#fbefd5;--danger:#b42318;--danger-bg:#fde3e1;--info:#0b5cad;--info-bg:#dfeefc;
--muted-bg:#eceff3;--s1:#9aa3b0;--s2:#0b63c5;--s3:#13753f}
*{box-sizing:border-box}html,body{margin:0}body{background:var(--bg);color:var(--text);font:14px/1.5 "Segoe UI",system-ui,-apple-system,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--panel);border-bottom:1px solid var(--border);padding:12px 20px;display:flex;flex-wrap:wrap;gap:10px;align-items:center}
header h1{font-size:18px;margin:0 12px 0 0}.spacer{flex:1}
.ctl{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
button,select{background:var(--code-bg);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:5px 10px;font:inherit;cursor:pointer}
button:hover{border-color:var(--accent)}
nav.tabs{display:flex;gap:4px;flex-wrap:wrap;padding:10px 20px 0;border-bottom:1px solid var(--border);background:var(--panel)}
.tab-btn{border:1px solid transparent;border-bottom:none;border-radius:8px 8px 0 0;background:transparent;color:var(--muted);padding:8px 14px}
.tab-btn.active{background:var(--bg);color:var(--text);border-color:var(--border)}
main{padding:18px 20px 60px;max-width:1500px;margin:0 auto}
.tab-pane{display:none}.tab-pane.active{display:block}
h2{font-size:17px;margin:22px 0 10px;border-bottom:1px solid var(--border);padding-bottom:6px}h3{font-size:15px;margin:18px 0 8px}
.tag{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600;white-space:nowrap;border:1px solid transparent}
.tag.good{color:var(--good);background:var(--good-bg)}.tag.warn{color:var(--warn);background:var(--warn-bg)}
.tag.danger{color:var(--danger);background:var(--danger-bg)}.tag.info{color:var(--info);background:var(--info-bg)}
.tag.muted{color:var(--muted);background:var(--muted-bg)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px;margin:10px 0}
.card{background:var(--panel);border:1px solid var(--border);border-left:4px solid var(--border);border-radius:8px;padding:10px 12px}
.card.good{border-left-color:var(--good)}.card.warn{border-left-color:var(--warn)}.card.danger{border-left-color:var(--danger)}.card.info{border-left-color:var(--info)}
.card .v{font-size:22px;font-weight:700}.card .l{color:var(--muted);font-size:12px}
.tbl-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:8px;background:var(--panel)}
table{border-collapse:collapse;width:100%}th,td{padding:7px 10px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}
th{background:var(--code-bg);color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.03em;position:sticky;top:0}
tr:last-child td{border-bottom:none}
code{background:var(--code-bg);padding:1px 5px;border-radius:4px;font-size:12.5px;word-break:break-all}
.muted{color:var(--muted)}details summary{cursor:pointer;color:var(--accent)}ul.ev{margin:6px 0 0 0;padding-left:18px}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin:10px 0}
.banner{border-radius:10px;padding:14px 18px;margin:10px 0;border:1px solid var(--border);background:var(--panel)}
.banner.good{border-color:var(--good)}.banner.danger{border-color:var(--danger)}.banner.warn{border-color:var(--warn)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
.cell{text-align:center;font-weight:600}
svg.chart{width:100%;max-width:900px;height:auto}svg .cl{fill:var(--muted);font-size:12px}svg .cv{fill:var(--text);font-size:11px}
.shot{max-width:100%;border:1px solid var(--border);border-radius:6px}
.filter{margin:8px 0}
td.f-good{background:var(--good-bg);color:var(--good);font-weight:700}
td.f-bad{background:var(--danger-bg);color:var(--danger);font-weight:700}
td.f-warn{background:var(--warn-bg);color:var(--warn);font-weight:700}
td.f-info{background:var(--info-bg);color:var(--info);font-weight:700}
td.f-muted{color:var(--muted)}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.hero{display:grid;grid-template-columns:auto 1fr;gap:18px;align-items:center;border-radius:12px;padding:18px 22px;
margin:6px 0 16px;border:2px solid var(--border);background:var(--panel)}
.hero.good{border-color:var(--good);background:var(--good-bg)}.hero.danger{border-color:var(--danger);background:var(--danger-bg)}
.hero.warn{border-color:var(--warn);background:var(--warn-bg)}
.hero .big{font-size:30px;font-weight:800;line-height:1.1}.hero .big small{display:block;font-size:12px;font-weight:600;
letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.hero p{margin:4px 0}.hero.good .big{color:var(--good)}.hero.danger .big{color:var(--danger)}.hero.warn .big{color:var(--warn)}
.lead{font-size:15px;margin:4px 0 14px}
.chips span{margin:0 4px 4px 0;display:inline-block}
@media (max-width:700px){header{padding:10px 16px}main{padding:14px 16px 50px}nav.tabs{padding:8px 16px 0}}
"""

JS = r"""
(function(){
  var root=document.documentElement, KEY='html-artifact-theme';
  function setTheme(t){root.setAttribute('data-theme',t);try{localStorage.setItem(KEY,t)}catch(e){}
    var b=document.getElementById('themeBtn'); if(b) b.textContent=t==='dark'?'Light mode':'Dark mode';}
  var saved='dark'; try{saved=localStorage.getItem(KEY)||'dark'}catch(e){}
  setTheme(saved);
  document.getElementById('themeBtn').addEventListener('click',function(){setTheme(root.getAttribute('data-theme')==='dark'?'light':'dark')});
  var btns=document.querySelectorAll('.tab-btn'), panes=document.querySelectorAll('.tab-pane');
  btns.forEach(function(b){b.addEventListener('click',function(){
    btns.forEach(function(x){x.classList.toggle('active',x===b)});
    panes.forEach(function(p){p.classList.toggle('active',p.id===b.dataset.tab)});
    stop();});});
  // status filter on checks tables
  document.querySelectorAll('select[data-filter]').forEach(function(sel){sel.addEventListener('change',function(){
    var t=document.getElementById(sel.dataset.filter); if(!t) return;
    t.querySelectorAll('tbody tr').forEach(function(tr){tr.style.display=(!sel.value||tr.dataset.status===sel.value)?'':'none'});});});
  // ---- Listen (Web Speech API, offline) ----
  var synth=window.speechSynthesis, vSel=document.getElementById('voiceSel'), rSel=document.getElementById('rateSel');
  var VK='html-artifact-voice', RK='html-artifact-rate', queue=[], speaking=false;
  if(!synth){document.getElementById('listen').style.display='none';return;}
  try{var r=localStorage.getItem(RK); if(r) rSel.value=r;}catch(e){}
  function loadVoices(){var vs=synth.getVoices(), want=''; try{want=localStorage.getItem(VK)||''}catch(e){}
    vSel.innerHTML=''; vs.forEach(function(v){var o=document.createElement('option');o.value=v.name;o.textContent=v.name+' ('+v.lang+')';if(v.name===want)o.selected=true;vSel.appendChild(o);});}
  loadVoices(); if(synth.onvoiceschanged!==undefined) synth.onvoiceschanged=loadVoices;
  vSel.addEventListener('change',function(){try{localStorage.setItem(VK,vSel.value)}catch(e){}});
  rSel.addEventListener('change',function(){try{localStorage.setItem(RK,rSel.value)}catch(e){}});
  function textOf(el){
    var out=[];
    (function walk(n){
      if(n.nodeType===3){var t=n.textContent.replace(/\s+/g,' ').trim(); if(t) out.push(t); return;}
      if(n.nodeType!==1) return;
      var tg=n.tagName; if(/^(SVG|SCRIPT|STYLE|BUTTON|SELECT|IMG|NOSCRIPT)$/i.test(tg)||n.classList.contains('no-read')) return;
      if(tg==='TABLE'){var hs=[].map.call(n.querySelectorAll('thead th'),function(h){return h.textContent.trim()});
        n.querySelectorAll('tbody tr').forEach(function(tr){ if(tr.style.display==='none') return;
          var cells=[].map.call(tr.children,function(td,i){var t=td.textContent.replace(/\s+/g,' ').trim(); return t?(hs[i]?hs[i]+': ':'')+t:''}).filter(Boolean);
          if(cells.length) out.push(cells.join(', ')+'.');}); return;}
      if(tg==='DETAILS' && !n.open){var s=n.querySelector('summary'); if(s) out.push(s.textContent.trim()+'.'); return;}
      [].forEach.call(n.childNodes,walk);
      if(/^(H1|H2|H3|P|LI|DIV)$/.test(tg)) out.push('. ');
    })(el);
    return out.join(' ').replace(/(\.\s*){2,}/g,'. ');
  }
  function chunks(t){var parts=t.match(/[^.!?]+[.!?]*/g)||[t], res=[], cur='';
    parts.forEach(function(p){ if((cur+p).length>220){ if(cur) res.push(cur); cur=p;} else cur+=p; }); if(cur.trim()) res.push(cur); return res;}
  function next(){ if(!queue.length){speaking=false;return;}
    var u=new SpeechSynthesisUtterance(queue.shift()); var v=synth.getVoices().filter(function(x){return x.name===vSel.value})[0];
    if(v) u.voice=v; u.rate=parseFloat(rSel.value)||1; u.onend=next; u.onerror=next; synth.speak(u);}
  function play(){ if(synth.paused){synth.resume();return;} if(speaking) return;
    var pane=document.querySelector('.tab-pane.active'); queue=chunks(textOf(pane)); speaking=true; next();}
  function stop(){queue=[];speaking=false;if(synth) synth.cancel();}
  document.getElementById('playBtn').addEventListener('click',play);
  document.getElementById('pauseBtn').addEventListener('click',function(){ if(synth.paused) synth.resume(); else synth.pause();});
  document.getElementById('stopBtn').addEventListener('click',stop);
})();
"""


def page(title: str, subtitle: str, tags: list[tuple[str, str]], tabs: list[tuple[str, str, str]]) -> str:
    """tabs = [(id, label, html)]; the first tab starts active. Every <details> starts expanded."""
    tabs = [(tid, label, body.replace("<details>", "<details open>")) for tid, label, body in tabs]
    tag_html = " ".join(tag(t, k) for t, k in tags)
    nav = "".join(f'<button class="tab-btn{" active" if i == 0 else ""}" data-tab="{esc(tid)}">{esc(label)}</button>'
                  for i, (tid, label, _) in enumerate(tabs))
    panes = "".join(f'<section class="tab-pane{" active" if i == 0 else ""}" id="{esc(tid)}">{body}</section>'
                    for i, (tid, _, body) in enumerate(tabs))
    return f"""<!doctype html>
<html lang="en" data-theme="dark"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head>
<body>
<header><h1>{esc(title)}</h1><span class="muted">{esc(subtitle)}</span> {tag_html}<span class="spacer"></span>
<div class="ctl" id="listen" aria-label="Listen"><span class="muted">Listen</span>
<button id="playBtn" title="Read the current tab aloud">Play</button><button id="pauseBtn">Pause</button><button id="stopBtn">Stop</button>
<select id="voiceSel" aria-label="Voice"></select>
<select id="rateSel" aria-label="Speed"><option value="0.75">0.75x</option><option value="1" selected>1x</option><option value="1.25">1.25x</option><option value="1.5">1.5x</option><option value="2">2x</option></select>
</div>
<button id="themeBtn">Light mode</button></header>
<nav class="tabs">{nav}</nav>
<main>{panes}</main>
<script>{JS}</script>
</body></html>"""
