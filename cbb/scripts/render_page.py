"""Render cbb/live/picks.json into a self-contained mobile-first picks board."""
import json
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
src = json.load(open("cbb/live/picks.json"))
out_path = sys.argv[1] if len(sys.argv) > 1 else "cbb/picks.html"

games = []
for g in src["games"]:
    t = datetime.fromisoformat(g["date"].replace("Z", "+00:00")).astimezone(ET)
    g["day"] = t.strftime("%Y-%m-%d")
    g["dayLabel"] = t.strftime("%a %b %-d")
    g["time"] = t.strftime("%-I:%M %p")
    g["ts"] = t.timestamp()
    games.append(g)
gen = datetime.fromisoformat(src["generated"].replace("Z", "+00:00")).astimezone(ET).strftime("%a %b %-d, %-I:%M %p ET")

html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CBB Style Model: Picks</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#16181d;--mute:#6b6f78;--line:#e6e3dc;--accent:#1f5eff;--strong:#0f8a4b;--play:#1f5eff;--lean:#9aa0aa;--warn:#b25e00;--chip:#f0eee9}
@media (prefers-color-scheme:dark){:root{--bg:#111316;--card:#191c21;--ink:#eceef2;--mute:#9298a3;--line:#2a2e35;--accent:#6b93ff;--strong:#3ccf86;--play:#6b93ff;--lean:#6d737d;--warn:#f0a050;--chip:#22262c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 Inter,system-ui,sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:18px 14px 60px}
h1{font-size:22px;margin:0 0 2px;letter-spacing:-.01em}.sub{color:var(--mute);font-size:13px}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:14px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px}
.stat b{display:block;font:600 18px 'JetBrains Mono',monospace}.stat span{color:var(--mute);font-size:11.5px}
details.how{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin-bottom:14px}
details.how summary{cursor:pointer;font-weight:600}details.how p,details.how li{color:var(--mute);font-size:13.5px}
.days{display:flex;gap:6px;overflow-x:auto;padding-bottom:6px;margin:4px 0 8px;scrollbar-width:none}
.days button,.filters button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:7px 12px;font:500 13px Inter;white-space:nowrap;cursor:pointer}
.days button.on,.filters button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.days button small{color:inherit;opacity:.6;margin-left:4px}
.filters{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin-bottom:10px}
.top{display:flex;justify-content:space-between;gap:8px;color:var(--mute);font-size:12.5px}
.match{font-weight:600;font-size:15.5px;margin:4px 0 8px}
.pickrow{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.pick{font:600 15px 'JetBrains Mono',monospace}
.tier{font:600 11px Inter;text-transform:uppercase;letter-spacing:.06em;padding:3px 8px;border-radius:6px;color:#fff}
.tier.strong{background:var(--strong)}.tier.play{background:var(--play)}.tier.lean{background:var(--lean)}
.edge{color:var(--mute);font-size:13px}
.badge{font-size:11px;padding:2px 7px;border-radius:6px;background:var(--chip);color:var(--mute)}
.badge.posted{color:var(--strong)}.badge.tempo{color:var(--warn)}
ul.why{margin:8px 0 0;padding-left:18px;font-size:13.5px}ul.why li{margin:2px 0}ul.why em{color:var(--mute);font-style:normal;font-family:'JetBrains Mono',monospace;font-size:12px}
.empty{color:var(--mute);text-align:center;padding:30px}
</style></head><body><div class="wrap">
<h1>CBB Style Model</h1>
<div class="sub">Picks vs the spread, next two weeks. Data as of __GEN__.</div>
<div class="stats">
<div class="stat"><b>54.0%</b><span>ATS at 1+ pt edge<br>10,270 out-of-sample bets</span></div>
<div class="stat"><b>57.2%</b><span>ATS at 2+ pt edge<br>1,511 bets</span></div>
<div class="stat"><b>54.3%</b><span>Early season (&lt;5 games)<br>59.4% at 2+ pts</span></div>
</div>
<details class="how"><summary>How it works</summary>
<p>The market prices teams on whether their shots fell. This model prices them on how they create and deny shots, which is more stable. It adds up the gaps between the two teams' profiles and predicts how many points one side beats the line by.</p>
<ul>
<li><b>Underpriced:</b> offensive rebounding, ball security, 3-point volume, assists, paint scoring, rim protection, and defenses that limit paint points, second chances and transition.</li>
<li><b>Overpriced:</b> teams whose opponents have shot poorly against them, and hot-shooting teams.</li>
<li><b>Tempo flag:</b> a fast favorite (8.5+) facing a slow underdog. Underdogs covered about 52% historically.</li>
<li><b>Tiers:</b> Strong = 2+ pt edge, Play = 1 to 2, Lean = under 1 (not a bet).</li>
<li><b>Posted vs projected:</b> posted lines come from the books. Further out, the line is projected from the same team profiles (typical miss 3.4 pts). Treat projected picks as a preview until the real number opens.</li>
<li>Early-season profiles blend this season's games with last season, weighted toward this season as games pile up.</li>
</ul></details>
<div class="days" id="days"></div>
<div class="filters" id="filters"></div>
<div id="list"></div>
</div>
<script>
const G=__DATA__;
const tiers=[["bets","Plays + Strong"],["strong","Strong only"],["all","All games"]];
let st={day:null,tier:"bets",posted:false};
try{const s=JSON.parse(localStorage.getItem("cbbf")||"{}");if(s.tier)st.tier=s.tier;if(s.posted)st.posted=s.posted}catch(e){}
const days=[...new Map(G.map(g=>[g.day,g.dayLabel])).entries()].sort();
st.day=days[0]?days[0][0]:null;
function pass(g){if(st.posted&&g.line_status!=="posted")return false;if(st.tier==="bets")return g.tier!=="lean";if(st.tier==="strong")return g.tier==="strong";return true}
function render(){
 const dEl=document.getElementById("days");dEl.innerHTML="";
 days.forEach(([d,l])=>{const n=G.filter(g=>g.day===d&&pass(g)).length;const b=document.createElement("button");b.className=d===st.day?"on":"";b.innerHTML=l+"<small>"+n+"</small>";b.onclick=()=>{st.day=d;render()};dEl.appendChild(b)});
 const fEl=document.getElementById("filters");fEl.innerHTML="";
 tiers.forEach(([k,l])=>{const b=document.createElement("button");b.className=st.tier===k?"on":"";b.textContent=l;b.onclick=()=>{st.tier=k;save();render()};fEl.appendChild(b)});
 const p=document.createElement("button");p.className=st.posted?"on":"";p.textContent="Posted lines only";p.onclick=()=>{st.posted=!st.posted;save();render()};fEl.appendChild(p);
 const rows=G.filter(g=>g.day===st.day&&pass(g)).sort((a,b)=>b.edge-a.edge||a.ts-b.ts);
 const L=document.getElementById("list");
 if(!rows.length){L.innerHTML='<div class="empty">No games match these filters on this day.</div>';return}
 L.innerHTML=rows.map(g=>{
  const sep=g.neutral?" vs ":" @ ";
  const line=g.line_status==="posted"?'<span class="badge posted">Line posted'+(g.book?" · "+g.book:"")+'</span>':'<span class="badge">Projected line</span>';
  const tempo=g.tempo_flag?'<span class="badge tempo">Tempo flag</span>':"";
  const why=g.reasons.length?'<ul class="why">'+g.reasons.map(r=>`<li>${r.text} <em>+${r.pts.toFixed(1)}</em></li>`).join("")+"</ul>":"";
  return `<div class="card"><div class="top"><span>${g.time}${g.venue?" · "+g.venue:""}</span><span>Games played ${g.games_played[0]}-${g.games_played[1]}</span></div>
  <div class="match">${g.away}${sep}${g.home}</div>
  <div class="pickrow"><span class="tier ${g.tier}">${g.tier}</span><span class="pick">${g.pick_line}</span><span class="edge">edge ${g.edge.toFixed(1)} pts</span></div>
  <div class="pickrow" style="margin-top:6px">${line}${tempo}</div>${why}</div>`}).join("");
}
function save(){try{localStorage.setItem("cbbf",JSON.stringify({tier:st.tier,posted:st.posted}))}catch(e){}}
render();
</script></body></html>"""
html = html.replace("__GEN__", gen).replace("__DATA__", json.dumps(games, separators=(",", ":")))
open(out_path, "w").write(html)
print("wrote", out_path, len(html), "bytes,", len(games), "games")
