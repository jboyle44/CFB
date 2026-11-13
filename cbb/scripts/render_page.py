"""Render the CBB Style Model board: Picks / Results / How it works.

Inputs: cbb/live/picks.json, cbb/live/ledger.json, cbb/results/trends.json
Usage: [DAYS=YYYY-MM-DD,...] [DAYS_AHEAD=n] python render_page.py OUT.html
"""
import json
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
out_path = sys.argv[1] if len(sys.argv) > 1 else "cbb/picks.html"
src = json.load(open("cbb/live/picks.json"))
ledger = json.load(open("cbb/live/ledger.json")) if os.path.exists("cbb/live/ledger.json") else {"entries": {}}
trends = json.load(open("cbb/results/trends.json"))

gen_dt = datetime.fromisoformat(src["generated"].replace("Z", "+00:00")).astimezone(ET)
DAYS = set(filter(None, os.environ.get("DAYS", "").split(",")))
if not DAYS and os.environ.get("DAYS_AHEAD"):
    DAYS = {(gen_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(int(os.environ["DAYS_AHEAD"]))}


def et(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(ET)


games = []
for g in src["games"]:
    t = et(g["date"])
    g["day"], g["dayLabel"], g["time"], g["ts"] = t.strftime("%Y-%m-%d"), t.strftime("%a %b %-d"), t.strftime("%-I:%M %p"), t.timestamp()
    if DAYS and g["day"] not in DAYS:
        continue
    games.append(g)

results = []
for e in ledger["entries"].values():
    t = et(e["date"])
    e["day"], e["dayLabel"], e["ts"] = t.strftime("%Y-%m-%d"), t.strftime("%a %b %-d"), t.timestamp()
    results.append(e)

data = {"games": games, "results": results, "trends": trends, "weights": src.get("weights", []), "weights_est": src.get("weights_established", []),
        "generated": gen_dt.strftime("%a %b %-d, %-I:%M %p ET")}

HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CBB Style Model: Picks</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#16181d;--mute:#6b6f78;--faint:#9aa0aa;--line:#e6e3dc;--accent:#1f5eff;--pos:#0f8a4b;--neg:#c2410c;--strong:#0f8a4b;--play:#1f5eff;--lean:#9aa0aa;--warn:#b25e00;--chip:#f0eee9}
@media (prefers-color-scheme:dark){:root{--bg:#111316;--card:#191c21;--ink:#eceef2;--mute:#9298a3;--faint:#6d737d;--line:#2a2e35;--accent:#6b93ff;--pos:#3ccf86;--neg:#ff8a5c;--strong:#3ccf86;--play:#6b93ff;--lean:#6d737d;--warn:#f0a050;--chip:#22262c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 Inter,system-ui,sans-serif}
.wrap{max-width:780px;margin:0 auto;padding:18px 14px 70px}
h1{font-size:22px;margin:0 0 2px;letter-spacing:-.01em}h2{font-size:17px;margin:22px 0 8px}h3{font-size:12.5px;margin:18px 0 6px;color:var(--mute);text-transform:uppercase;letter-spacing:.05em}
.sub{color:var(--mute);font-size:13px}p{margin:6px 0}.note{color:var(--mute);font-size:13px}
.tabs{display:flex;gap:4px;margin:14px 0 12px;border-bottom:1px solid var(--line)}
.tabs button{border:0;background:none;color:var(--mute);font:600 14px Inter;padding:9px 12px;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px}
.tabs button.on{color:var(--ink);border-bottom-color:var(--ink)}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px}
.stat b{display:block;font:600 18px 'JetBrains Mono',monospace}.stat span{color:var(--mute);font-size:11.5px}
.days{display:flex;gap:6px;overflow-x:auto;padding-bottom:6px;margin:4px 0 8px;scrollbar-width:none}
.days button,.filters button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:7px 12px;font:500 13px Inter;white-space:nowrap;cursor:pointer}
.days button.on,.filters button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.days button small{opacity:.6;margin-left:4px}
.filters{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin-bottom:10px}
.top{display:flex;justify-content:space-between;gap:8px;color:var(--mute);font-size:12.5px}
.match{font-weight:600;font-size:15.5px;margin:4px 0 8px}
.pickrow{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.pick{font:600 15px 'JetBrains Mono',monospace}
.tier{font:600 11px Inter;text-transform:uppercase;letter-spacing:.06em;padding:3px 8px;border-radius:6px;color:#fff}
.tier.strong{background:var(--strong)}.tier.play{background:var(--play)}.tier.lean{background:var(--lean)}
.edge{color:var(--mute);font-size:13px}
.badge{font-size:11px;padding:2px 7px;border-radius:6px;background:var(--chip);color:var(--mute)}
.badge.posted{color:var(--pos)}.badge.tempo{color:var(--warn)}
ul.why{margin:8px 0 0;padding-left:18px;font-size:13.5px}ul.why li{margin:2px 0}
.mono{font-family:'JetBrains Mono',monospace;font-size:12.5px}
.pos{color:var(--pos)}.neg{color:var(--neg)}.mut{color:var(--faint)}
details.prof{margin-top:10px;border-top:1px solid var(--line);padding-top:8px}
details.prof summary{cursor:pointer;font-weight:600;font-size:13px;color:var(--accent)}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}
th{text-align:right;color:var(--mute);font-weight:500;font-size:11.5px;padding:4px 6px;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
td{padding:4px 6px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums}
tr.grp td{color:var(--mute);font-size:11px;text-transform:uppercase;letter-spacing:.05em;padding-top:10px;border-bottom:0}
tr.total td{font-weight:700;border-bottom:0}
.wl{display:inline-block;min-width:20px;text-align:center;font:700 11px Inter;padding:2px 5px;border-radius:5px;color:#fff}
.wl.W{background:var(--pos)}.wl.L{background:var(--neg)}.wl.P{background:var(--lean)}
.box{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin-bottom:12px;overflow-x:auto}
.bar{display:inline-block;height:8px;border-radius:4px;vertical-align:middle}
.chartwrap{position:relative}
.tip{position:absolute;pointer-events:none;background:var(--ink);color:var(--bg);font-size:12px;padding:5px 8px;border-radius:6px;white-space:nowrap;display:none}
.empty{color:var(--mute);text-align:center;padding:30px}
</style></head><body><div class="wrap">
<h1>CBB Style Model</h1>
<div class="sub">Picks vs the spread. Data as of <span id="gen"></span>.</div>
<div class="tabs" id="tabs"></div>
<div id="view"></div>
</div>
<script>
const D=__DATA__;
document.getElementById("gen").textContent=D.generated;
const TABS=[["picks","Picks"],["results","Results"],["trends","Trends"],["how-it-works","How it works"]];
let trSeason="all";
let tab=(location.hash||"#picks").slice(1);if(!TABS.some(t=>t[0]===tab))tab="picks";
let st={day:null,tier:"bets",posted:false};
try{const s=JSON.parse(localStorage.getItem("cbbf")||"{}");if(s.tier)st.tier=s.tier;if(s.posted)st.posted=s.posted}catch(e){}
const days=[...new Map(D.games.map(g=>[g.day,g.dayLabel])).entries()].sort();
st.day=days.length?days[0][0]:null;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const sgn=v=>(v>0?"+":v<0?"−":"")+Math.abs(v).toFixed(2);
const sgn1=v=>(v>0?"+":v<0?"−":"")+Math.abs(v).toFixed(1);
const cls=v=>v>0.005?"pos":v<-0.005?"neg":"mut";
function save(){try{localStorage.setItem("cbbf",JSON.stringify({tier:st.tier,posted:st.posted}))}catch(e){}}
function tabs(){document.getElementById("tabs").innerHTML=TABS.map(([k,l])=>`<button class="${k===tab?"on":""}" data-t="${k}">${l}</button>`).join("");
 document.querySelectorAll("#tabs button").forEach(b=>b.onclick=()=>{tab=b.dataset.t;try{history.replaceState(null,"","#"+tab)}catch(e){location.hash=tab}render()})}
window.addEventListener("hashchange",()=>{const h=location.hash.slice(1);if(TABS.some(t=>t[0]===h)){tab=h;render()}});
function pass(g){if(st.posted&&g.line_status!=="posted")return false;if(st.tier==="bets")return g.tier!=="lean";if(st.tier==="strong")return g.tier==="strong";return true}

function profile(g){
 const fmt=(t,v)=>t.kind==="pct"?v.toFixed(1)+"%":v.toFixed(1);
 const ord={Tempo:0,Offense:1,Defense:2};let rows="";let grp="";
 const tr=[...g.traits].sort((a,b)=>(ord[a.group]-ord[b.group])||Math.abs(b.pts)-Math.abs(a.pts));
 for(const t of tr){if(t.group!==grp){grp=t.group;rows+=`<tr class="grp"><td colspan="4">${grp}</td></tr>`}
  rows+=`<tr><td>${esc(t.label)}</td><td>${fmt(t,t.away)}</td><td>${fmt(t,t.home)}</td><td class="mono ${cls(t.pts)}">${sgn(t.pts)}</td></tr>`}
 rows+=`<tr class="grp"><td colspan="4">Adjustments</td></tr>`;
 for(const t of g.terms)rows+=`<tr><td>${esc(t.label)}</td><td></td><td></td><td class="mono ${cls(t.pts)}">${sgn(t.pts)}</td></tr>`;
 rows+=`<tr class="total"><td>Model edge for ${esc(g.pick)}</td><td></td><td></td><td class="mono">${sgn(g.edge)}</td></tr>`;
 const ref=g.spread_home!=null?g.spread_home:g.proj_spread_home, pickHome=g.pick===g.home;
 const sp=pickHome?ref:-ref, fair=sp-g.edge;
 const ln=v=>Math.abs(v)<0.05?"PK":(v>0?"+":"−")+Math.abs(v).toFixed(1);
 rows+=`<tr class="grp"><td colspan="4">The line</td></tr>
 <tr><td>${g.line_status==="posted"?"Posted spread"+(g.book?" ("+esc(g.book)+")":""):"Projected spread (no line posted yet)"}</td><td colspan="3" class="mono">${esc(g.pick)} ${ln(sp)}</td></tr>
 <tr class="total"><td>Model's fair line</td><td colspan="3" class="mono">${esc(g.pick)} ${ln(fair)}</td></tr>`;
 return `<details class="prof"><summary>Full profile: all 19 traits and points</summary>
 <table><thead><tr><th>Trait (season so far, blended)</th><th>${esc(g.away)}</th><th>${esc(g.home)}</th><th>Pts to pick</th></tr></thead><tbody>${rows}</tbody></table>
 <div class="note" style="margin-top:6px">Pts to pick: how many points each trait gap adds (+) or subtracts (−) from the pick's edge. They sum to the edge.</div></details>`}

function vPicks(){
 let h=`<div class="days">`+days.map(([d,l])=>{const n=D.games.filter(g=>g.day===d&&pass(g)).length;return `<button class="${d===st.day?"on":""}" data-d="${d}">${l}<small>${n}</small></button>`}).join("")+`</div>`;
 h+=`<div class="filters">`+[["bets","Plays + Strong"],["strong","Strong only"],["all","All games"]].map(([k,l])=>`<button class="${st.tier===k?"on":""}" data-f="${k}">${l}</button>`).join("")+`<button class="${st.posted?"on":""}" data-p="1">Posted lines only</button></div>`;
 const rows=D.games.filter(g=>g.day===st.day&&pass(g)).sort((a,b)=>b.edge-a.edge||a.ts-b.ts);
 if(!rows.length)h+=`<div class="empty">No games match these filters on this day.</div>`;
 h+=rows.map(g=>{const sep=g.neutral?" vs ":" @ ";
  const line=g.line_status==="posted"?`<span class="badge posted">Line posted${g.book?" · "+esc(g.book):""}</span>`:`<span class="badge">Projected line</span>`;
  const isDog=g.pick_line.includes("+");
  const tempo=g.tempo_flag?(isDog?`<span class="badge tempo">Tempo agrees: slow dog vs fast favorite</span>`:`<span class="badge">Tempo cuts against: dog is slower</span>`):"";
  const why=g.reasons.length?`<ul class="why">`+g.reasons.map(r=>`<li>${esc(r.text)} <span class="mono pos">+${r.pts.toFixed(1)}</span></li>`).join("")+`</ul>`:"";
  return `<div class="card"><div class="top"><span>${g.time}${g.venue?" · "+esc(g.venue):""}</span><span>Games played ${g.games_played[0]}-${g.games_played[1]}</span></div>
  <div class="match">${esc(g.away)}${sep}${esc(g.home)}</div>
  <div class="pickrow"><span class="tier ${g.tier}">${g.tier}</span><span class="pick">${esc(g.pick_line)}</span><span class="edge">edge ${g.edge.toFixed(1)} pts</span></div>
  <div class="pickrow" style="margin-top:6px">${line}${tempo}<span class="badge">${g.model==="established"?"Established model (5+ games)":"Early-season model"}</span></div>${why}${profile(g)}</div>`}).join("");
 return h}

function rec(list){const w=list.filter(e=>e.result==="W").length,l=list.filter(e=>e.result==="L").length,p=list.filter(e=>e.result==="P").length;
 return {w,l,p,n:w+l,pct:w+l?100*w/(w+l):null,u:w*100/110-l}}
function vResults(){
 const done=D.results.filter(e=>e.result),pend=D.results.filter(e=>!e.result);
 const plays=done.filter(e=>e.tier!=="lean"),strong=done.filter(e=>e.tier==="strong"),leans=done.filter(e=>e.tier==="lean");
 const tile=(r,lab)=>`<div class="stat"><b>${r.w}-${r.l}${r.p?"-"+r.p:""}</b><span>${lab}<br>${r.pct==null?"—":r.pct.toFixed(1)+"%"} · ${sgn1(r.u)} units</span></div>`;
 let h=`<div class="stats">${tile(rec(plays),"All plays (1+ pt)")}${tile(rec(strong),"Strong (2+ pts)")}${tile(rec(leans),"Leans (not bets)")}</div>`;
 h+=`<p class="note">Picks are graded at the last posted line on the board before tip-off, 1 unit per bet at −110. Projected-line picks are never graded. ${pend.filter(e=>e.tier!=="lean").length} plays locked and awaiting results.</p>`;
 const byDay=[...new Set(done.map(e=>e.day))].sort().reverse();
 if(byDay.length){h+=`<h2>By day</h2><div class="box"><table><thead><tr><th>Day</th><th>Plays</th><th>Strong</th><th>Units</th></tr></thead><tbody>`+
  byDay.map(d=>{const L=done.filter(e=>e.day===d);const p=rec(L.filter(e=>e.tier!=="lean")),s=rec(L.filter(e=>e.tier==="strong"));
   return `<tr><td>${L[0].dayLabel}</td><td>${p.w}-${p.l}${p.p?"-"+p.p:""}</td><td>${s.w}-${s.l}</td><td class="mono ${cls(p.u)}">${sgn1(p.u)}</td></tr>`}).join("")+`</tbody></table></div>`}
 const recent=done.slice().sort((a,b)=>b.ts-a.ts||b.edge-a.edge);
 h+=`<h2>Graded picks</h2><div class="box">`+
  (recent.length?recent.map(e=>`<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--line)"><span class="wl ${e.result}" style="align-self:flex-start;margin-top:2px">${e.result}</span><div style="flex:1"><div><b class="mono">${esc(e.pick_line)}</b> <span class="mut">· edge ${e.edge.toFixed(1)} · ${e.tier}</span></div><div class="note">${esc(e.away)} ${e.away_score}, ${esc(e.home)} ${e.home_score} · ${e.dayLabel} · ${e.result==="P"?"push":(e.result==="W"?"covered by ":"missed by ")+Math.abs(e.margin_vs_line).toFixed(1)}</div></div></div>`).join(""):`<div class="empty">No graded picks yet.</div>`)+`</div>`;
 const pp=pend.filter(e=>e.tier!=="lean").sort((a,b)=>a.ts-b.ts||b.edge-a.edge);
 if(pp.length)h+=`<h2>Locked, awaiting results</h2><div class="box"><table><thead><tr><th>Pick</th><th>Tier</th><th>Edge</th><th>Tip</th></tr></thead><tbody>`+
  pp.map(e=>`<tr><td>${esc(e.pick_line)}</td><td>${e.tier}</td><td class="mono">${e.edge.toFixed(1)}</td><td>${e.dayLabel}</td></tr>`).join("")+`</tbody></table></div>`;
 return h}

function tbl(head,rows){return `<div class="box"><table><thead><tr>${head.map(x=>`<th>${x}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`}
const pc=s=>s&&s.bets?`${s.win_pct.toFixed(1)}%`:"—";
const pcCls=s=>s&&s.bets?(s.win_pct>=52.4?"pos":"neg"):"mut";
function vHow(){
 const T=D.trends,O=T.overall;
 let h=`<h2>The idea</h2><p><b>The market prices teams on scoring margin, and the model says margin built on winning the possession battle holds up better than margin built on shot-making.</b></p>
 <p class="note">Shooting percentages, for and against, swing a lot on luck. Rebounding, turnovers, shot volume, paint scoring and rim protection are stable skills. Lines lean on margin, which mixes the two; the model reads the stable part and discounts the luck (early in the season, partly by blending each team's shooting with last season's). The gap is widest early in the season, when samples are small.</p>
 <h2>How a pick is made</h2><ol class="note" style="padding-left:18px">
 <li>Build each team's profile: 19 traits from its games so far. Until both teams have 5 games, profiles are blended with last season (early-season model); after that, only this season counts (established model). Only games before tip-off are used.</li>
 <li>Compare the two teams trait by trait, in standard-deviation units.</li>
 <li>Multiply each gap by the trait's learned weight (table below) and add the underdog adjustment. The total is the edge: points the pick is expected to beat the line by.</li>
 <li>Bet at 1+ pt of edge (Play) and 2+ pts (Strong). Under 1 pt is a Lean, not a bet.</li></ol>`;
 const W=D.weights.filter(w=>w.key!=="spread").sort((a,b)=>Math.abs(b.pts_per_sd)-Math.abs(a.pts_per_sd));
 const WE=Object.fromEntries((D.weights_est||[]).map(w=>[w.key,w.pts_per_sd]));
 const mx=Math.max(...W.map(w=>Math.abs(w.pts_per_sd)));
 h+=`<h2>What the model rewards</h2><p class="note">Points of edge for being 1 standard deviation higher than the opponent in a trait, holding the rest fixed. + means the market underrates the trait, − means it overrates it.</p>`+
  tbl(["Trait","Early season","","Established"],W.map(w=>`<tr><td>${esc(w.label)}<div class="mut" style="font-size:11px">${w.group}</div></td><td class="mono ${cls(w.pts_per_sd)}">${sgn(w.pts_per_sd)}</td><td style="width:84px;text-align:left"><span class="bar" style="width:${Math.round(76*Math.abs(w.pts_per_sd)/mx)}px;background:var(--${w.pts_per_sd>0?"pos":"neg"})"></span></td><td class="mono ${cls(WE[w.key]||0)}">${WE[w.key]!=null?sgn(WE[w.key]):"—"}</td></tr>`))+`<p class="note">Early season = blended with last season (either team under 5 games). Established = this season only, once both teams have 5+ games; it leans harder on fading shooting results because those numbers are no longer shrunk toward last season.</p>`;
 h+=`<h2>Backtest</h2><p class="note">${esc(T.model)}. Each season is predicted by a model trained only on earlier seasons and graded against the closing spread at −110. Breakeven is 52.4%.</p>
 <div class="stats"><div class="stat"><b>${O.plays_1plus.win_pct}%</b><span>Plays (1+ pt)<br>${O.plays_1plus.bets.toLocaleString()} bets · ${sgn1(O.plays_1plus.units)} u</span></div>
 <div class="stat"><b>${O.strong_2plus.win_pct}%</b><span>Strong (2+ pts)<br>${O.strong_2plus.bets.toLocaleString()} bets · ${sgn1(O.strong_2plus.units)} u</span></div>
 <div class="stat"><b>${T.by_month[0].strong.win_pct}%</b><span>November, Strong<br>${T.by_month[0].strong.bets.toLocaleString()} bets</span></div></div>
 <h3>Cumulative units, plays (1+ pt), 2016-17 to 2025-26</h3><div class="box chartwrap" id="cw"><svg id="cum" width="100%" height="220" role="img" aria-label="Cumulative units won by season"></svg><div class="tip" id="tip"></div></div>
 <h3>By month: the edge is early-season</h3>`+
  tbl(["Month","Plays","Win %","Units","Strong win %"],T.by_month.map(m=>`<tr><td>${m.month}</td><td>${m.plays.bets.toLocaleString()}</td><td class="${pcCls(m.plays)}">${pc(m.plays)}</td><td class="mono ${cls(m.plays.units)}">${sgn1(m.plays.units)}</td><td class="${pcCls(m.strong)}">${pc(m.strong)} <span class="mut">(${m.strong.bets})</span></td></tr>`))+
 `<h3>By edge size: bigger edges win more</h3>`+
  tbl(["Edge","Games","Win %","Units"],T.by_edge.map(e=>`<tr><td>${e.edge} pts</td><td>${e.bets.toLocaleString()}</td><td class="${pcCls(e)}">${pc(e)}</td><td class="mono ${cls(e.units)}">${sgn1(e.units)}</td></tr>`))+
 `<h3>By season</h3>`+
  tbl(["Season","Plays","Win %","Units","Strong win %"],T.by_season.map(s=>`<tr><td>${s.season}</td><td>${s.plays.bets.toLocaleString()}</td><td class="${pcCls(s.plays)}">${pc(s.plays)}</td><td class="mono ${cls(s.plays.units)}">${sgn1(s.plays.units)}</td><td class="${pcCls(s.strong)}">${pc(s.strong)}</td></tr>`))+
 `<h3>Underdog vs favorite picks (1+ pt)</h3>`+
  tbl(["Side","Bets","Win %","Units"],T.by_side.map(s=>`<tr><td>${s.side}</td><td>${s.bets.toLocaleString()}</td><td class="${pcCls(s)}">${pc(s)}</td><td class="mono ${cls(s.units)}">${sgn1(s.units)}</td></tr>`))+
 `<h2>Fine print</h2><ul class="note" style="padding-left:18px">
 <li>Tempo flag: a fast favorite (8.5+) vs a slow underdog. Underdogs covered about 52% historically; it supports dog picks and cuts against favorite picks.</li>
 <li>Projected lines (before books post) come from the same profiles and miss the real close by about 3.4 pts on average. Treat those picks as previews.</li>
 <li>Lines before 2019 cover about 65% of games. Results assume −110; real prices and limits vary, especially on low-major games and big underdogs.</li>
 <li>Style-vs-style matchups (archetypes, shot-mix clashes) were tested and do not beat the spread. Only tempo survived.</li></ul>`;
 return h}

function tcell(c,isLean){if(!c||!c.n)return `<td class="mut">—</td>`;
 const k=isLean?"":(c.pct>=52.4?"pos":"neg");
 return `<td><span class="mono ${k}" style="font-weight:600">${c.pct.toFixed(1)}%</span><div class="mut" style="font-size:11px">${c.n.toLocaleString()} games</div></td>`}
function trow(label,t,bold){return `<tr${bold?' class="total"':""}><td>${label}</td>${tcell(t.strong)}${tcell(t.play)}${tcell(t.lean,true)}</tr>`}
function vTrends(){
 const G=D.trends.tier_grid;const seasons=Object.keys(G).filter(k=>k!=="all");
 const head=`<thead><tr><th>${"%s"}</th><th>Strong<br><span class="mut">2+ pts</span></th><th>Play<br><span class="mut">1 to 2 pts</span></th><th>Lean<br><span class="mut">under 1 pt</span></th></tr></thead>`;
 let h=`<p class="note">Backtest of the live model: each season predicted by a model trained only on earlier seasons, graded against the closing spread. Win % excludes pushes. Breakeven at −110 is 52.4% (green above, red below). Leans are not bets; they're shown for comparison.</p>`;
 h+=`<h2>By season</h2><div class="box"><table>${head.replace("%s","Season")}<tbody>`+seasons.map(s=>trow(s,G[s].total)).join("")+trow("All seasons",G.all.total,true)+`</tbody></table></div>`;
 const sel=G[trSeason]?trSeason:"all";
 h+=`<h2>By month</h2><div class="days">`+[["all","All seasons"],...seasons.map(s=>[s,s])].map(([k,l])=>`<button class="${k===sel?"on":""}" data-s="${k}">${l}</button>`).join("")+`</div>`;
 const M=G[sel].months;
 h+=`<div class="box"><table>${head.replace("%s","Month")}<tbody>`+Object.keys(M).filter(m=>M[m].strong.n+M[m].play.n+M[m].lean.n>0).map(m=>trow(m,M[m])).join("")+trow(sel==="all"?"All months":sel+" total",G[sel].total,true)+`</tbody></table></div>`;
 h+=`<p class="note">April has only a handful of games per season (postseason), so treat its percentages as noise.</p>`;
 return h}

function chart(){
 const svg=document.getElementById("cum");if(!svg)return;const P=D.trends.cumulative;if(P.length<2)return;
 const W=svg.clientWidth||700,H=220,m={l:44,r:12,t:12,b:26};
 const ys=P.map(p=>p.units),ymin=Math.min(0,...ys),ymax=Math.max(...ys);
 const x=i=>m.l+(W-m.l-m.r)*i/(P.length-1),y=v=>m.t+(H-m.t-m.b)*(1-(v-ymin)/(ymax-ymin||1));
 const css=getComputedStyle(document.documentElement),c=n=>css.getPropertyValue(n).trim();
 let g="";const span=ymax-ymin||1;const tick=span>300?100:span>120?50:25;
 for(let v=Math.ceil(ymin/tick)*tick;v<=ymax;v+=tick)g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${y(v)}" y2="${y(v)}" stroke="${c("--line")}" stroke-width="1"/><text x="${m.l-6}" y="${y(v)+4}" text-anchor="end" font-size="11" fill="${c("--mute")}">${v}</text>`;
 let last="";P.forEach((p,i)=>{const yr=+p.date.slice(0,4),mo=+p.date.slice(5,7);const lab=mo>=8?`${String(yr).slice(2)}-${String(yr+1).slice(2)}`:`${String(yr-1).slice(2)}-${String(yr).slice(2)}`;
  if(lab!==last){last=lab;if(i>0)g+=`<line x1="${x(i)}" x2="${x(i)}" y1="${m.t}" y2="${H-m.b}" stroke="${c("--line")}" stroke-dasharray="2 3"/>`;if(W>420||i%2===0)g+=`<text x="${x(i)+3}" y="${H-8}" font-size="10" fill="${c("--mute")}">${lab}</text>`}});
 g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${y(0)}" y2="${y(0)}" stroke="${c("--faint")}" stroke-width="1"/>`;
 g+=`<path d="${P.map((p,i)=>(i?"L":"M")+x(i).toFixed(1)+" "+y(p.units).toFixed(1)).join("")}" fill="none" stroke="${c("--accent")}" stroke-width="2" stroke-linejoin="round"/>`;
 g+=`<line id="xh" x1="0" x2="0" y1="${m.t}" y2="${H-m.b}" stroke="${c("--mute")}" stroke-width="1" visibility="hidden"/><circle id="dot" r="4" fill="${c("--accent")}" stroke="${c("--card")}" stroke-width="2" visibility="hidden"/>`;
 g+=`<rect x="${m.l}" y="${m.t}" width="${W-m.l-m.r}" height="${H-m.t-m.b}" fill="transparent" id="hit"/>`;
 svg.innerHTML=g;const tip=document.getElementById("tip"),xh=document.getElementById("xh"),dot=document.getElementById("dot");
 const move=ev=>{const r=svg.getBoundingClientRect();const cx=(ev.touches?ev.touches[0].clientX:ev.clientX)-r.left;let i=Math.round((cx-m.l)/(W-m.l-m.r)*(P.length-1));i=Math.max(0,Math.min(P.length-1,i));
  const px=x(i),py=y(P[i].units);xh.setAttribute("x1",px);xh.setAttribute("x2",px);xh.setAttribute("visibility","visible");dot.setAttribute("cx",px);dot.setAttribute("cy",py);dot.setAttribute("visibility","visible");
  tip.style.display="block";tip.textContent=`${P[i].date}: ${P[i].units>0?"+":""}${P[i].units} units`;tip.style.left=Math.min(px+10,W-150)+"px";tip.style.top=Math.max(py-30,0)+"px"};
 const hide=()=>{tip.style.display="none";xh.setAttribute("visibility","hidden");dot.setAttribute("visibility","hidden")};
 const hit=document.getElementById("hit");hit.addEventListener("mousemove",move);hit.addEventListener("touchmove",move,{passive:true});hit.addEventListener("mouseleave",hide);hit.addEventListener("touchend",hide)}

function render(){tabs();const v=document.getElementById("view");
 v.innerHTML=tab==="picks"?vPicks():tab==="results"?vResults():tab==="trends"?vTrends():vHow();
 if(tab==="trends")v.querySelectorAll("[data-s]").forEach(b=>b.onclick=()=>{trSeason=b.dataset.s;render()});
 if(tab==="picks"){v.querySelectorAll("[data-d]").forEach(b=>b.onclick=()=>{st.day=b.dataset.d;render()});
  v.querySelectorAll("[data-f]").forEach(b=>b.onclick=()=>{st.tier=b.dataset.f;save();render()});
  v.querySelectorAll("[data-p]").forEach(b=>b.onclick=()=>{st.posted=!st.posted;save();render()})}
 if(tab==="how-it-works")chart()}
render();window.addEventListener("resize",()=>{if(tab==="how-it-works")chart()});
</script></body></html>"""

html = HTML.replace("__DATA__", json.dumps(data, separators=(",", ":")))
open(out_path, "w").write(html)
print("wrote", out_path, f"{len(html)/1024:.0f} KB,", len(games), "games,", len(results), "ledger entries")
