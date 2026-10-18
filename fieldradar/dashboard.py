"""Builds dashboard.html — a single self-contained page (works offline)."""
import json
from collections import Counter
from datetime import datetime, timezone

FIELDS = ["id", "title", "link", "source", "venue", "published", "first_seen", "evidence",
          "evidence_label", "group", "flags", "tags", "primary", "score", "deadline",
          "deadline_what", "days_left", "is_new"]


def pick_top(items, n):
    """Best-scoring new items, max 2 per interest area so one topic can't take over."""
    fresh = [i for i in items if i["is_new"]]
    if len(fresh) < n:  # quiet day: fall back to the most recently found items
        recent_ids = {i["id"] for i in sorted(items, key=lambda i: i["first_seen"], reverse=True)[: n * 6]}
        fresh = [i for i in items if i["is_new"] or i["id"] in recent_ids]
    per_area, out = Counter(), []
    for it in sorted(fresh, key=lambda i: i["score"], reverse=True):
        if per_area[it["primary"]] >= 2:
            continue
        per_area[it["primary"]] += 1
        out.append(it)
        if len(out) >= n:
            break
    return out


def _deadlines(items, manual):
    today = datetime.now(timezone.utc).date()
    rows, unknown = [], []
    for d in manual:
        row = {"title": d.get("title", ""), "what": d.get("what", ""), "url": d.get("url", ""),
               "type": d.get("type", "other"), "notes": d.get("notes", ""), "auto": False}
        date = str(d.get("date") or "").strip()
        if date:
            try:
                dd = datetime.fromisoformat(date).date()
            except ValueError:
                unknown.append(row)
                continue
            row["date"], row["days_left"] = dd.isoformat(), (dd - today).days
            rows.append(row)
        else:
            unknown.append(row)
    for it in items:
        if it.get("deadline"):
            rows.append({"title": it["title"], "what": it["deadline_what"], "url": it["link"],
                         "type": "phd" if it["evidence"] == "phd" else "conference" if it["evidence"] == "cfp" else "other",
                         "notes": it["source"], "date": it["deadline"], "days_left": it["days_left"], "auto": True})
    rows.sort(key=lambda r: r["date"])
    return rows, unknown


def build(path, items, config, manual_deadlines, meta):
    settings = config.get("settings", {})
    picks = pick_top(items, int(settings.get("top_picks", 10)))
    pick_ids = [p["id"] for p in picks]
    deadlines, unknown = _deadlines(items, manual_deadlines)
    data = {
        "meta": meta,
        "interests": [{"id": i["id"], "name": i["name"], "icon": i.get("icon", "•")} for i in config["interests"]]
                     + [{"id": "opportunities", "name": "PhDs & Conferences", "icon": "🎯"}],
        "items": [dict({k: it.get(k) for k in FIELDS}, summary=it.get("ai_summary") or it.get("summary") or "")
                  for it in sorted(items, key=lambda i: i["score"], reverse=True)],
        "picks": pick_ids,
        "deadlines": deadlines,
        "unknown": unknown,
    }
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    path.write_text(TEMPLATE.replace("__DATA__", blob), encoding="utf-8")
    return picks


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#f6f5f1" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#151513" media="(prefers-color-scheme: dark)">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Field Radar">
<meta name="mobile-web-app-capable" content="yes">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 100 100%27><text y=%27.9em%27 font-size=%2790%27>📡</text></svg>">
<title>Field Radar</title>
<style>
:root{
  --bg:#f6f5f1; --panel:#ffffff; --ink:#1d1d1b; --muted:#6b6a64; --line:#e4e1d8; --accent:#2d5b8a;
  --research:#1f7a5a; --research-bg:#e3f2ea; --meta:#0f5c41; --meta-bg:#cdebdc;
  --practice:#2d5b8a; --practice-bg:#e2ecf6; --news:#6b6a64; --news-bg:#eeede8;
  --opp:#9a5b00; --opp-bg:#fbeed6; --new:#c2410c; --warn:#b42318; --warn-bg:#fde7e5;
  --shadow:0 1px 2px rgba(0,0,0,.05);
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#151513; --panel:#1f1f1c; --ink:#ecebe6; --muted:#a3a29b; --line:#33322e; --accent:#8db8e8;
    --research:#7fd3ae; --research-bg:#1d3329; --meta:#a4e6c8; --meta-bg:#22402f;
    --practice:#8db8e8; --practice-bg:#1e2c3b; --news:#b5b4ad; --news-bg:#2a2a26;
    --opp:#f2c46d; --opp-bg:#3a2e17; --new:#fb923c; --warn:#ff8a7a; --warn-bg:#3d1f1b;
    --shadow:none;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:inherit}
.wrap{max-width:980px;margin:0 auto;padding:20px 16px 60px}
header h1{margin:0;font-size:26px;letter-spacing:-.01em}
header p{margin:4px 0 0;color:var(--muted);font-size:14px}
.stats{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 6px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:4px 12px;font-size:13px}
.stat b{font-variant-numeric:tabular-nums}
nav{display:flex;gap:6px;overflow-x:auto;padding:12px 0 10px;margin:0 -16px;padding-left:16px;padding-right:16px;
    position:sticky;top:0;background:var(--bg);z-index:5;border-bottom:1px solid var(--line);scrollbar-width:thin}
nav button{flex:none;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:999px;
    padding:6px 12px;font:inherit;font-size:13.5px;cursor:pointer;white-space:nowrap}
nav button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
nav button .n{opacity:.6;margin-left:4px;font-variant-numeric:tabular-nums}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}
.controls input[type=search]{flex:1 1 220px;min-width:0;padding:8px 12px;border:1px solid var(--line);border-radius:8px;
    background:var(--panel);color:var(--ink);font:inherit}
.controls select,.controls label{padding:7px 10px;border:1px solid var(--line);border-radius:8px;background:var(--panel);
    color:var(--ink);font:inherit;font-size:14px}
.controls label{display:flex;align-items:center;gap:6px;cursor:pointer}
.intro{color:var(--muted);font-size:14px;margin:6px 0 14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0;box-shadow:var(--shadow)}
.card.read{opacity:.62}
.top{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.pill{font-size:12px;font-weight:600;border-radius:6px;padding:2px 8px;white-space:nowrap}
.g-research{color:var(--research);background:var(--research-bg)}
.e-meta,.e-experiment{color:var(--meta);background:var(--meta-bg)}
.g-practice{color:var(--practice);background:var(--practice-bg)}
.g-news{color:var(--news);background:var(--news-bg)}
.g-opportunity{color:var(--opp);background:var(--opp-bg)}
.flag{font-size:12px;border:1px solid var(--line);border-radius:6px;padding:1px 7px;color:var(--muted)}
.newb{font-size:11px;font-weight:700;color:var(--new);letter-spacing:.04em}
.dl{font-size:12px;font-weight:600;border-radius:6px;padding:2px 8px;color:var(--opp);background:var(--opp-bg)}
.dl.urgent{color:var(--warn);background:var(--warn-bg)}
.save{margin-left:auto;border:none;background:none;color:var(--muted);font-size:18px;cursor:pointer;padding:0 2px;line-height:1}
.save.on{color:#d4a017}
.card h3{margin:0;font-size:16.5px;line-height:1.35}
.card h3 a{text-decoration:none}
.card h3 a:hover{text-decoration:underline}
.src{color:var(--muted);font-size:13px;margin:4px 0 6px}
.sum{margin:0;font-size:14.5px}
.sum.none{color:var(--muted);font-style:italic;font-size:13.5px}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.tag{font-size:12px;color:var(--muted);background:var(--bg);border-radius:999px;padding:1px 9px;cursor:pointer;border:none;font:inherit;font-size:12px}
.empty{color:var(--muted);text-align:center;padding:40px 10px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top;font-size:14px}
th{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600}
tr.past td{opacity:.5}
.days{font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap}
.days.urgent{color:var(--warn)} .days.soon{color:var(--opp)}
h2{font-size:18px;margin:26px 0 8px}
.muted{color:var(--muted)}
.ok{color:var(--research)} .bad{color:var(--warn)}
.legend div{margin:6px 0}
.tablewrap{overflow-x:auto}
@media (max-width:600px){ th:nth-child(4),td:nth-child(4){display:none} .card{padding:12px} }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Field Radar</h1>
    <p id="sub"></p>
    <div class="stats" id="stats"></div>
  </header>
  <nav id="tabs"></nav>
  <div class="controls" id="controls">
    <input type="search" id="q" placeholder="Search titles, sources, summaries…">
    <select id="ev">
      <option value="all">All evidence types</option>
      <option value="research">Research only</option>
      <option value="strong">Strong evidence (reviews, experiments, peer-reviewed)</option>
      <option value="practice">Practice &amp; industry</option>
      <option value="news">News &amp; opinion</option>
      <option value="opportunity">Opportunities</option>
    </select>
    <select id="sort"><option value="score">Most relevant</option><option value="date">Newest</option></select>
    <label><input type="checkbox" id="newonly"> New only</label>
  </div>
  <main id="main"></main>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const mem = {
  get(k, d){ try{ return JSON.parse(localStorage.getItem('fr_'+k)) ?? d }catch(e){ return d } },
  set(k, v){ try{ localStorage.setItem('fr_'+k, JSON.stringify(v)) }catch(e){} }
};
let saved = new Set(mem.get('saved', [])), read = new Set(mem.get('read', []));
let state = {tab: mem.get('tab', 'top'), q:'', ev:'all', sort:'score', newOnly:false};
const AREA = Object.fromEntries(D.interests.map(i => [i.id, i]));
const byId = Object.fromEntries(D.items.map(i => [i.id, i]));
// NEW = found since you last opened this page (remembered in this browser/phone)
const lastSeen = mem.get('seen_until', null);
D.items.forEach(i => { i.fresh = lastSeen ? i.first_seen > lastSeen : i.is_new; });
const markSeen = () => mem.set('seen_until', D.meta.generated);
addEventListener('pagehide', markSeen);
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') markSeen(); });
const fmt = iso => iso ? new Date(iso).toLocaleDateString(undefined, {day:'numeric', month:'short', year:'numeric'}) : '';

const gen = new Date(D.meta.generated);
$('#sub').textContent = 'Applied & Organizational Psychology · L&D · Behavioral Science — updated ' +
  gen.toLocaleString(undefined, {weekday:'short', day:'numeric', month:'short', hour:'2-digit', minute:'2-digit'});
const newCount = D.items.filter(i => i.fresh).length;
const soon = D.deadlines.filter(d => d.days_left >= 0 && d.days_left <= 30).length;
$('#stats').innerHTML =
  `<span class="stat"><b>${newCount}</b> new since your last visit</span>` +
  `<span class="stat"><b>${D.items.length}</b> relevant items</span>` +
  `<span class="stat"><b>${D.items.filter(i => ['meta','experiment','peer'].includes(i.evidence)).length}</b> peer-reviewed</span>` +
  `<span class="stat"><b>${soon}</b> deadlines in 30 days</span>`;

function tabsList(){
  const count = id => D.items.filter(i => (i.tags || []).includes(id)).length;
  return [
    {id:'top', label:'⭐ Top picks', n: D.picks.length},
    {id:'all', label:'All', n: D.items.length},
    ...D.interests.map(i => ({id:i.id, label:`${i.icon} ${i.name}`, n: count(i.id)})),
    {id:'deadlines', label:'⏰ Deadlines', n: D.deadlines.filter(d => d.days_left >= 0).length},
    {id:'saved', label:'🔖 Saved', n: saved.size},
    {id:'about', label:'⚙ Sources & help'},
  ];
}
function renderTabs(){
  $('#tabs').innerHTML = tabsList().map(t =>
    `<button data-tab="${t.id}" class="${state.tab===t.id?'on':''}">${esc(t.label)}${t.n!=null?`<span class="n">${t.n}</span>`:''}</button>`).join('');
}

function matches(i){
  if (state.newOnly && !i.fresh) return false;
  const ev = state.ev;
  if (ev === 'strong' && !['meta','experiment','peer'].includes(i.evidence)) return false;
  if (!['all','strong'].includes(ev) && i.group !== ev) return false;
  if (state.q){
    const hay = (i.title+' '+i.summary+' '+i.source+' '+(i.venue||'')).toLowerCase();
    if (!state.q.toLowerCase().split(/\s+/).every(w => hay.includes(w))) return false;
  }
  return true;
}

function card(i){
  const ev = `<span class="pill g-${i.group} e-${i.evidence}">${esc(i.evidence_label)}</span>`;
  const flags = (i.flags||[]).map(f => `<span class="flag">${esc(f)}</span>`).join('');
  let dl = '';
  if (i.deadline){
    const cls = i.days_left <= 14 ? 'dl urgent' : 'dl';
    dl = `<span class="${cls}">⏰ ${esc(i.deadline_what)} ${fmt(i.deadline)} · ${i.days_left}d</span>`;
  }
  const when = i.published || i.first_seen;
  const src = [i.source, i.venue && i.venue !== i.source ? i.venue : '', fmt(when)].filter(Boolean).map(esc).join(' · ');
  const sum = i.summary ? `<p class="sum">${esc(i.summary)}</p>`
                        : `<p class="sum none">No description from the source — open the link to read.</p>`;
  const tags = (i.tags||[]).filter(t => AREA[t]).map(t => `<button class="tag" data-tab="${t}">${AREA[t].icon} ${esc(AREA[t].name)}</button>`).join('');
  return `<article class="card ${read.has(i.id)?'read':''}" data-id="${i.id}">
    <div class="top">${ev}${flags}${dl}${i.fresh?'<span class="newb">NEW</span>':''}
      <button class="save ${saved.has(i.id)?'on':''}" title="Save for later" aria-label="Save">${saved.has(i.id)?'★':'☆'}</button></div>
    <h3><a href="${esc(i.link)}" target="_blank" rel="noopener">${esc(i.title)}</a></h3>
    <div class="src">${src}</div>${sum}<div class="tags">${tags}</div></article>`;
}

function list(items, intro){
  items = items.filter(matches);
  if (state.sort === 'date') items.sort((a,b) => (b.published||b.first_seen).localeCompare(a.published||a.first_seen));
  const head = intro ? `<p class="intro">${intro}</p>` : '';
  return head + (items.length ? items.map(card).join('') : `<div class="empty">Nothing here with the current filters.</div>`);
}

function deadlinesView(){
  const row = d => {
    const cls = d.days_left < 0 ? 'past' : '';
    const dc = d.days_left <= 14 ? 'urgent' : d.days_left <= 45 ? 'soon' : '';
    const left = d.days_left < 0 ? 'passed' : d.days_left === 0 ? 'today' : `${d.days_left} days`;
    return `<tr class="${cls}"><td class="days ${dc}">${left}</td><td>${fmt(d.date)}</td>
      <td><a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a><div class="muted">${esc(d.what)}</div></td>
      <td class="muted">${d.auto ? 'Found automatically · '+esc(d.notes) : esc(d.notes)}</td></tr>`;
  };
  const up = D.deadlines.filter(d => d.days_left >= 0);
  let h = `<p class="intro">Deadlines found automatically in PhD and conference listings, plus the ones you added in <b>deadlines.toml</b>.
    Always confirm dates on the official page.</p>`;
  h += up.length ? `<div class="tablewrap"><table><thead><tr><th>Left</th><th>Date</th><th>What</th><th>Notes</th></tr></thead><tbody>${up.map(row).join('')}</tbody></table></div>`
                 : `<div class="empty">No dated deadlines yet. Add dates in deadlines.toml.</div>`;
  if (D.unknown.length){
    h += `<h2>Dates to confirm</h2><p class="intro">Open the official page, find the current deadline, and add it to <b>deadlines.toml</b> as YYYY-MM-DD.</p>
      <div class="tablewrap"><table><thead><tr><th>Type</th><th>Programme / event</th><th>Notes</th></tr></thead><tbody>` +
      D.unknown.map(d => `<tr><td class="muted">${esc(d.type)}</td><td><a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a>
        <div class="muted">${esc(d.what)}</div></td><td class="muted">${esc(d.notes)}</td></tr>`).join('') + `</tbody></table></div>`;
  }
  return h;
}

function aboutView(){
  const s = D.meta.sources || [];
  const rows = s.map(x => `<tr><td class="${x.ok?'ok':'bad'}">${x.ok?'✓':'✗'}</td><td>${esc(x.name)}</td>
    <td class="days">${x.found}</td><td class="days">${x.new}</td><td class="muted">${esc(x.error)}</td></tr>`).join('');
  return `<h2>How to read the labels</h2><div class="legend">
    <div><span class="pill e-meta">Meta-analysis / Review</span> pools many studies. Strongest evidence.</div>
    <div><span class="pill e-experiment">Experiment / RCT</span> tests cause and effect.</div>
    <div><span class="pill g-research">Peer-reviewed</span> published in an academic journal after expert review.</div>
    <div><span class="pill g-research">Preprint · not yet peer-reviewed</span> new research, still unchecked by reviewers.</div>
    <div><span class="pill g-research">Research news</span> a journalist's write-up of a study. Follow the link to the original.</div>
    <div><span class="pill g-practice">Industry report / survey</span> useful, but often run by companies with an interest in the result.</div>
    <div><span class="pill g-practice">Practitioner article</span> expert experience and frameworks, not data.</div>
    <div><span class="pill g-news">News</span> / <span class="pill g-news">Opinion / blog</span> awareness only, not evidence.</div>
    <div><span class="pill g-opportunity">PhD / research position</span> <span class="pill g-opportunity">Conference / call for papers</span> opportunities.</div>
  </div>
  <h2>How ranking works</h2>
  <p class="muted">Each item gets points for matching your keywords (config.toml), for stronger evidence, for being recent,
  and, for PhDs, for being funded or in Europe and for having a near deadline. Fluffy headlines ("10 tips…") and off-topic
  subjects lose points. Items under the minimum score are hidden. Edit config.toml to tune it.</p>
  <h2>Last fetch</h2>
  ${s.length ? `<div class="tablewrap"><table><thead><tr><th></th><th>Source</th><th>Found</th><th>New</th><th>Problem</th></tr></thead><tbody>${rows}</tbody></table></div>`
             : '<p class="muted">This page was rebuilt offline.</p>'}`;
}

function render(){
  renderTabs();
  const t = state.tab;
  $('#controls').style.display = ['deadlines','about'].includes(t) ? 'none' : '';
  let h;
  if (t === 'top') h = list(D.picks.map(id => byId[id]).filter(Boolean),
      'The most relevant new items, with at most two per interest area. Ranked by keyword match, evidence strength, recency and deadlines.');
  else if (t === 'all') h = list(D.items.slice());
  else if (t === 'deadlines') h = deadlinesView();
  else if (t === 'about') h = aboutView();
  else if (t === 'saved') h = list(D.items.filter(i => saved.has(i.id)), 'Items you starred. Saved in this browser only.');
  else h = list(D.items.filter(i => (i.tags||[]).includes(t)));
  $('#main').innerHTML = h;
}

$('#tabs').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return;
  state.tab = b.dataset.tab; mem.set('tab', state.tab); render(); });
$('#main').addEventListener('click', e => {
  const tag = e.target.closest('.tag'); if (tag){ state.tab = tag.dataset.tab; mem.set('tab', state.tab); render(); scrollTo(0,0); return; }
  const c = e.target.closest('.card'); if (!c) return;
  const id = c.dataset.id;
  if (e.target.closest('.save')){ saved.has(id) ? saved.delete(id) : saved.add(id); mem.set('saved', [...saved]); render(); return; }
  if (e.target.closest('h3 a')){ read.add(id); mem.set('read', [...read].slice(-3000)); c.classList.add('read'); }
});
$('#q').addEventListener('input', e => { state.q = e.target.value.trim(); render(); });
$('#ev').addEventListener('change', e => { state.ev = e.target.value; render(); });
$('#sort').addEventListener('change', e => { state.sort = e.target.value; render(); });
$('#newonly').addEventListener('change', e => { state.newOnly = e.target.checked; render(); });
if (!tabsList().some(t => t.id === state.tab)) state.tab = 'top';
render();
</script>
</body>
</html>
"""
