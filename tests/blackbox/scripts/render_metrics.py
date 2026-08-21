#!/usr/bin/env python3
"""Render a metrics.json evaluation report into a self-contained, interactive HTML dashboard.

The dashboard is a single HTML file (data embedded inline) that visualizes the run with
Chart.js: summary KPI cards, token/latency/LLM/tool charts, success gauges, a scatter of
tokens-vs-latency, and a searchable, expandable table of every scenario, query response,
and per-expectation score/reason.

When a baseline metrics JSON is available (``baseline_metrics.json`` next to the input by
default, or ``--baseline PATH``), per-scenario charts show current vs baseline side by side
and the KPI cards and scenario table annotate each numeric value with the delta vs baseline
(red ▲/▼ = degraded, green = improved). Pie/doughnut charts show the current run only.

Usage:
    python scripts/render_metrics.py                       # metrics.json -> metrics_report.html
    python scripts/render_metrics.py path/to/metrics.json  # custom input
    python scripts/render_metrics.py in.json -o out.html   # custom input + output
    python scripts/render_metrics.py -b baseline.json      # explicit baseline for comparison
    python scripts/render_metrics.py --open                # open in the default browser

The output is fully offline-capable except for the Chart.js and marked.js CDN script tags.
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

# Chart.js is loaded from a CDN. Override with --chartjs-src for an offline/self-hosted copy.
DEFAULT_CHARTJS_SRC = "https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"


def load_report(path: Path) -> dict:
    """Read and parse the metrics JSON report."""
    try:
        with path.open(encoding="utf-8") as file:
            data: dict = json.load(file)
            return data
    except FileNotFoundError:
        sys.exit(f"error: input file not found: {path}")
    except json.JSONDecodeError as exc:
        sys.exit(f"error: could not parse JSON in {path}: {exc}")


def load_baseline(path: Path) -> dict:
    """Read and parse an optional baseline metrics report. Returns {} if not found."""
    try:
        with path.open(encoding="utf-8") as file:
            data: dict = json.load(file)
            return data
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        sys.exit(f"error: could not parse baseline JSON in {path}: {exc}")


def build_html(report: dict, baseline: dict, *, source_name: str, baseline_name: str, chartjs_src: str) -> str:
    """Build the full HTML dashboard string with the report (and baseline) data embedded inline."""
    data_json = json.dumps(report, default=str)
    baseline_json = json.dumps(baseline or {}, default=str)
    # Guard against the closing-script-tag injection when embedding JSON in a <script> block.
    data_json = data_json.replace("</", "<\\/")
    baseline_json = baseline_json.replace("</", "<\\/")
    return _HTML_TEMPLATE.format(
        source_name=_escape(source_name),
        baseline_name=_escape(baseline_name) if baseline_name else "",
        chartjs_src=chartjs_src,
        data_json=data_json,
        baseline_json=baseline_json,
        styles=_STYLES,
        script=_SCRIPT,
    )


def _escape(text: str) -> str:
    """Minimal HTML escaping for text interpolated into the template."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


_STYLES = """
:root {
  --bg: #0f1420; --panel: #171d2e; --panel-2: #1e2740; --border: #2a3652;
  --text: #e6ebf5; --muted: #8ea0c0; --accent: #4f8cff; --accent-2: #7c5cff;
  --ok: #3fb950; --warn: #d29922; --bad: #f85149; --chip: #223052;
}
* { box-sizing: border-box; }
body {
  margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: radial-gradient(1200px 600px at 20% -10%, #1a2440 0%, var(--bg) 55%); color: var(--text);
}
header { padding: 28px 32px 8px; }
h1 { margin: 0 0 4px; font-size: 24px; letter-spacing: .2px; }
.sub { color: var(--muted); font-size: 13px; }
main { padding: 16px 32px 64px; max-width: 1500px; margin: 0 auto; }
section { margin-top: 28px; }
h2 { font-size: 15px; text-transform: uppercase; letter-spacing: 1.2px; color: var(--muted); margin: 0 0 12px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }
.card {
  background: linear-gradient(180deg, var(--panel-2), var(--panel)); border: 1px solid var(--border);
  border-radius: 14px; padding: 16px 18px;
}
.card .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .6px; }
.card .value { font-size: 26px; font-weight: 700; margin-top: 6px; }
.card .value small { font-size: 13px; color: var(--muted); font-weight: 500; }
.grid { display: grid; grid-template-columns: 1fr; gap: 18px; }
.grid-3 { display: grid; grid-template-columns: 1fr; gap: 18px; }
.pie-row { display: flex; flex-direction: row; flex-wrap: wrap; gap: 18px; }
.pie-row .chart-box { flex: 1 1 300px; min-width: 260px; }
@media (max-width: 720px) { .pie-row { flex-direction: column; } }
.chart-box {
  background: linear-gradient(180deg, var(--panel-2), var(--panel)); border: 1px solid var(--border);
  border-radius: 14px; padding: 16px 18px;
}
.chart-box h3 { margin: 0 0 12px; font-size: 14px; font-weight: 600; }
.chart-wrap { position: relative; height: 300px; }
.chart-wrap.tall { height: 380px; }
.controls { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
.controls input, .controls select {
  background: var(--panel); border: 1px solid var(--border); color: var(--text);
  border-radius: 8px; padding: 8px 10px; font-size: 13px;
}
.controls input { min-width: 260px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }
th { color: var(--muted); font-weight: 600; cursor: pointer; user-select: none; white-space: nowrap; }
th:hover { color: var(--text); }
tbody tr:hover { background: rgba(79,140,255,.06); }
.badge { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11.5px; font-weight: 600; }
.b-ok { background: rgba(63,185,80,.16); color: #6ee787; }
.b-bad { background: rgba(248,81,73,.16); color: #ff7b72; }
.b-pending { background: rgba(210,153,34,.16); color: #e3b341; }
.b-neutral { background: var(--chip); color: var(--muted); }
.expand-btn { cursor: pointer; color: var(--accent); user-select: none; font-weight: 600; }
tbody tr.main-row { cursor: pointer; }
.detail-row td { background: rgba(0,0,0,.18); }
.q { border-left: 3px solid var(--border); padding: 12px 14px; margin: 10px 0; border-radius: 8px; background: var(--panel); }
.q.qok { border-left-color: var(--ok); }
.q.qbad { border-left-color: var(--bad); }
.q .query-text { font-weight: 600; margin-bottom: 6px; }
.q .meta { color: var(--muted); font-size: 12px; margin-bottom: 8px; display: flex; gap: 14px; flex-wrap: wrap; }
.resp {
  white-space: pre-wrap; background: #0d1220; border: 1px solid var(--border); border-radius: 8px;
  padding: 10px 12px; font-size: 12.5px; max-height: 260px; overflow: auto; color: #cdd7ec;
}
.resp.md { white-space: normal; line-height: 1.5; }
.resp.md p { margin: 0 0 8px; }
.resp.md p:last-child { margin-bottom: 0; }
.resp.md h1, .resp.md h2, .resp.md h3, .resp.md h4 { margin: 12px 0 6px; font-size: 13.5px; }
.resp.md ul, .resp.md ol { margin: 6px 0; padding-left: 20px; }
.resp.md li { margin: 2px 0; }
.resp.md code { background: rgba(255,255,255,.08); padding: 1px 5px; border-radius: 4px; font-size: 12px; }
.resp.md pre { background: rgba(255,255,255,.06); border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px; overflow: auto; }
.resp.md pre code { background: none; padding: 0; }
.resp.md a { color: var(--accent); }
.resp.md table { width: auto; margin: 6px 0; font-size: 12px; }
.resp.md th, .resp.md td { border: 1px solid var(--border); padding: 4px 8px; }
.resp.md blockquote { border-left: 3px solid var(--border); margin: 6px 0; padding: 2px 10px; color: var(--muted); }
.exp { margin-top: 10px; }
.exp-item { border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; margin-top: 8px; }
.exp-head { display: flex; justify-content: space-between; gap: 10px; align-items: center; }
.exp-name { font-weight: 600; }
.exp-reason { color: var(--muted); font-size: 12px; margin-top: 6px; }
.bar { height: 6px; border-radius: 999px; background: var(--border); margin-top: 6px; overflow: hidden; }
.bar > span { display: block; height: 100%; }
.kv { color: var(--muted); font-size: 12px; }
.delta { font-size: 11px; font-weight: 700; margin-left: 6px; white-space: nowrap; }
.delta.bad { color: var(--bad); }
.delta.good { color: var(--ok); }
.delta.same { color: var(--muted); font-weight: 500; }
.card .delta { display: inline-block; margin: 6px 0 0; font-size: 12px; }
.empty { color: var(--muted); padding: 20px; text-align: center; }
.model-table { width: auto; min-width: 420px; }
.model-table th { cursor: default; }
.model-table td, .model-table th { padding: 7px 16px 7px 0; border-bottom: 1px solid var(--border); }
.model-table td:first-child { white-space: nowrap; }
footer { color: var(--muted); font-size: 12px; padding: 24px 32px; text-align: center; }
a { color: var(--accent); }
"""

_SCRIPT = r"""
const REPORT = window.__METRICS__ || {};
const summary = REPORT.summary || {};
const scenarios = REPORT.scenarios || [];
const run = REPORT.run || {};

const BASELINE = window.__BASELINE__ || {};
const baseSummary = BASELINE.summary || {};
const baseScenarios = BASELINE.scenarios || [];
const baseRun = BASELINE.run || {};
const HAS_BASELINE = baseScenarios.length > 0 || Object.keys(baseSummary).length > 0;
const baseById = {};
baseScenarios.forEach(s => { if (s && s.scenario_id) baseById[s.scenario_id] = s; });
function baseOf(id){ return baseById[id] || null; }

const PALETTE = ['#4f8cff','#7c5cff','#3fb950','#d29922','#f85149','#22d3ee','#e879f9','#f472b6','#a3e635','#fb923c'];
const fmt = (n, d=0) => (n===undefined||n===null||isNaN(n)) ? '0' : Number(n).toLocaleString(undefined,{maximumFractionDigits:d});
const esc = (s) => (s===undefined||s===null) ? '' : String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function renderMarkdown(text){
  if (text===undefined||text===null) return '';
  if (window.marked && typeof window.marked.parse === 'function'){
    try { return window.marked.parse(String(text)); } catch(e){ /* fall through */ }
  }
  return esc(text);
}

function el(id){ return document.getElementById(id); }

/* ---------- baseline delta helpers ----------
 * lowerIsBetter=true  -> an increase vs baseline is a degradation (red).
 * Returns an inline HTML snippet appended after the current value. */
function deltaHTML(cur, base, d=0, lowerIsBetter=true){
  if (!HAS_BASELINE || base===undefined || base===null || isNaN(base)) return '';
  cur = Number(cur)||0; base = Number(base)||0;
  const diff = cur - base;
  if (Math.abs(diff) < (d>0 ? Math.pow(10,-d)/2 : 0.5)) return ' <span class="delta same">–</span>';
  const up = diff > 0;
  const degraded = lowerIsBetter ? up : !up;
  const cls = degraded ? 'bad' : 'good';
  const icon = up ? '▲' : '▼';
  return ` <span class="delta ${cls}" title="baseline ${fmt(base,d)}">${icon} ${fmt(Math.abs(diff),d)}</span>`;
}

function statusBadge(status, passed){
  const s = (status||'').toLowerCase();
  if (s==='pending') return '<span class="badge b-pending">pending</span>';
  if (passed===false || s==='failed') return '<span class="badge b-bad">failed</span>';
  return '<span class="badge b-ok">'+esc(s||'passed')+'</span>';
}

/* ---------- KPI cards ---------- */
function renderCards(){
  const sc = summary.status_counts || {};
  const scen = sc.scenarios || {}; const q = sc.queries || {};
  const cards = [
    ['Scenarios', fmt(summary.num_scenarios), (scen.passed!==undefined? `${fmt(scen.passed)} passed / ${fmt(scen.failed)} failed`:''), ''],
    ['Queries', fmt(summary.num_queries), (q.passed!==undefined? `${fmt(q.passed)} ok / ${fmt(q.failed)} fail / ${fmt(q.pending)} pend`:''), ''],
    ['Success rate', fmt(summary.overall_success_rate,2)+'<small>%</small>', '', deltaHTML(summary.overall_success_rate, baseSummary.overall_success_rate, 2, false)],
    ['Total tokens', fmt(summary.total_tokens), `${fmt(summary.input_tokens)} in / ${fmt(summary.output_tokens)} out`, deltaHTML(summary.total_tokens, baseSummary.total_tokens, 0, true)],
    ['Avg tokens / query', fmt(summary.avg_tokens_per_query,0), '', deltaHTML(summary.avg_tokens_per_query, baseSummary.avg_tokens_per_query, 0, true)],
    ['Total latency', fmt(summary.total_latency_seconds,1)+'<small>s</small>', `avg ${fmt(summary.avg_latency_seconds,2)}s`, deltaHTML(summary.total_latency_seconds, baseSummary.total_latency_seconds, 1, true)],
    ['LLM calls', fmt(summary.total_llm_call_count), '', deltaHTML(summary.total_llm_call_count, baseSummary.total_llm_call_count, 0, true)],
    ['Tool calls', fmt(summary.total_tool_call_count), '', deltaHTML(summary.total_tool_call_count, baseSummary.total_tool_call_count, 0, true)],
    ['Run time', fmt(summary.total_time_minutes,2)+'<small>min</small>', run.model_name? esc(run.model_name):'', deltaHTML(summary.total_time_minutes, baseSummary.total_time_minutes, 2, true)],
  ];
  el('cards').innerHTML = cards.map(([label,value,sub,delta]) =>
    `<div class="card"><div class="label">${label}</div><div class="value">${value}${delta||''}</div>${sub?`<div class="kv" style="margin-top:6px">${sub}</div>`:''}</div>`
  ).join('');
}

/* ---------- chart helpers ---------- */
const baseOpts = (extra={}) => Object.assign({
  responsive:true, maintainAspectRatio:false,
  plugins:{ legend:{ labels:{ color:'#8ea0c0', font:{size:11} } } },
  scales:{ x:{ ticks:{color:'#8ea0c0',font:{size:10}}, grid:{color:'rgba(255,255,255,.05)'} },
           y:{ ticks:{color:'#8ea0c0',font:{size:10}}, grid:{color:'rgba(255,255,255,.05)'} } }
}, extra);

function mkChart(id, config){ const c = el(id); if(c) new Chart(c.getContext('2d'), config); }

/* scenarios that actually ran (have tokens or latency) sorted by tokens desc */
function runScenarios(){
  return scenarios.filter(s => (s.total_tokens||0) > 0 || (s.total_latency_seconds||0) > 0)
                  .slice().sort((a,b)=> (b.total_tokens||0)-(a.total_tokens||0));
}

function renderCharts(){
  const active = runScenarios();
  const labels = active.map(s => s.scenario_id);
  const baseFor = (arr, key) => active.map(s => { const b = baseOf(s.scenario_id); return b ? (b[key]||0) : 0; });
  const CUR = '#4f8cff', BASE = '#5b6b8c';

  // Total tokens per scenario (current vs baseline)
  const tokDs = [{ label:'current', data:active.map(s=>s.total_tokens||0), backgroundColor:CUR }];
  if (HAS_BASELINE) tokDs.push({ label:'baseline', data:baseFor(active,'total_tokens'), backgroundColor:BASE });
  mkChart('chTokens', { type:'bar', data:{ labels, datasets:tokDs },
    options: baseOpts({ scales:{ x:{ ticks:{color:'#8ea0c0',font:{size:9}}, grid:{display:false}},
      y:{ ticks:{color:'#8ea0c0'}, grid:{color:'rgba(255,255,255,.05)'}} } }) });

  // Latency per scenario (current vs baseline)
  const latDs = [{ label:'current (s)', data:active.map(s=>s.total_latency_seconds||0), backgroundColor:'#22d3ee' }];
  if (HAS_BASELINE) latDs.push({ label:'baseline (s)', data:baseFor(active,'total_latency_seconds'), backgroundColor:BASE });
  mkChart('chLatency', { type:'bar', data:{ labels, datasets:latDs }, options: baseOpts() });

  // LLM calls per scenario (current vs baseline)
  const llmDs = [{ label:'current', data:active.map(s=>s.llm_call_count||0), backgroundColor:'#3fb950' }];
  if (HAS_BASELINE) llmDs.push({ label:'baseline', data:baseFor(active,'llm_call_count'), backgroundColor:BASE });
  mkChart('chLlm', { type:'bar', data:{ labels, datasets:llmDs }, options: baseOpts() });

  // Tool calls per scenario (current vs baseline)
  const toolDs = [{ label:'current', data:active.map(s=>s.tool_call_count||0), backgroundColor:'#d29922' }];
  if (HAS_BASELINE) toolDs.push({ label:'baseline', data:baseFor(active,'tool_call_count'), backgroundColor:BASE });
  mkChart('chToolCalls', { type:'bar', data:{ labels, datasets:toolDs }, options: baseOpts() });

  // Scenario status donut
  const sc = summary.status_counts || {}; const scen = sc.scenarios || {};
  mkChart('chStatus', { type:'doughnut', data:{ labels:['passed','failed'],
      datasets:[{ data:[scen.passed||0, scen.failed||0], backgroundColor:['#3fb950','#f85149'], borderColor:'#171d2e', borderWidth:2 }]},
      options:{ responsive:true, maintainAspectRatio:false, cutout:'62%', plugins:{legend:{position:'bottom', labels:{color:'#8ea0c0'}}} } });

  // Query status donut
  const q = sc.queries || {};
  mkChart('chQueryStatus', { type:'doughnut', data:{ labels:['passed','failed','pending'],
      datasets:[{ data:[q.passed||0,q.failed||0,q.pending||0], backgroundColor:['#3fb950','#f85149','#d29922'], borderColor:'#171d2e', borderWidth:2 }]},
      options:{ responsive:true, maintainAspectRatio:false, cutout:'62%', plugins:{legend:{position:'bottom', labels:{color:'#8ea0c0'}}} } });

  // Tool usage
  const tc = summary.tool_call_counts || {};
  const tNames = Object.keys(tc);
  mkChart('chTools', { type:'doughnut', data:{ labels:tNames.length?tNames:['none'],
      datasets:[{ data:tNames.length?tNames.map(n=>tc[n]):[1], backgroundColor:PALETTE, borderColor:'#171d2e', borderWidth:2 }]},
      options:{ responsive:true, maintainAspectRatio:false, cutout:'55%', plugins:{legend:{position:'bottom', labels:{color:'#8ea0c0'}}} } });

  // Tokens vs latency scatter (per scenario) — current vs baseline
  const scatterDs = [{ label:'current',
      data: active.map(s=>({ x:s.total_latency_seconds||0, y:s.total_tokens||0, id:s.scenario_id })),
      backgroundColor:'#4f8cff' }];
  if (HAS_BASELINE) scatterDs.push({ label:'baseline',
      data: active.map(s=>{ const b=baseOf(s.scenario_id); return b?{ x:b.total_latency_seconds||0, y:b.total_tokens||0, id:s.scenario_id }:null; }).filter(Boolean),
      backgroundColor:'#5b6b8c' });
  mkChart('chScatter', { type:'scatter', data:{ datasets:scatterDs },
      options: baseOpts({ plugins:{ legend:{display:HAS_BASELINE}, tooltip:{ callbacks:{
        label:(ctx)=>`${ctx.raw.id}: ${fmt(ctx.raw.y)} tok, ${fmt(ctx.raw.x,2)}s` } } },
        scales:{ x:{ title:{display:true,text:'latency (s)',color:'#8ea0c0'}, ticks:{color:'#8ea0c0'}, grid:{color:'rgba(255,255,255,.05)'} },
                 y:{ title:{display:true,text:'total tokens',color:'#8ea0c0'}, ticks:{color:'#8ea0c0'}, grid:{color:'rgba(255,255,255,.05)'} } } }) });

  // Expectation score distribution (histogram over all expectations that have a score)
  const scores = [];
  scenarios.forEach(s => (s.queries||[]).forEach(qq => (qq.expectations||[]).forEach(e => {
    if (e.score !== null && e.score !== undefined) scores.push(Number(e.score));
  })));
  const bins = [0,0,0,0,0]; // [0-.2)(.2-.4)(.4-.6)(.6-.8)(.8-1]
  scores.forEach(v => { let i = Math.min(4, Math.floor(v*5)); if (v>=1) i=4; bins[i]++; });
  mkChart('chScores', { type:'bar', data:{ labels:['0–0.2','0.2–0.4','0.4–0.6','0.6–0.8','0.8–1.0'],
      datasets:[{ label:'expectations', data:bins,
        backgroundColor:['#f85149','#fb923c','#d29922','#a3e635','#3fb950'] }]},
      options: baseOpts({ plugins:{legend:{display:false}} }) });
  if (!scores.length) el('scoresNote').textContent = 'No per-expectation scores recorded in this report.';
}

/* ---------- flatten queries for the scatter/legend and the table ---------- */
function buildRows(){
  const rows = [];
  scenarios.forEach(s => {
    rows.push({ scenario: s, queries: s.queries||[] });
  });
  return rows;
}

let sortKey = 'total_tokens', sortDir = -1;
function renderTable(){
  const filter = (el('search').value || '').toLowerCase();
  const statusSel = el('statusFilter').value;
  let rows = buildRows();

  rows = rows.filter(({scenario}) => {
    const st = (scenario.status||'').toLowerCase();
    const passed = scenario.passed !== false;
    if (statusSel==='passed' && !(passed && st!=='pending')) return false;
    if (statusSel==='failed' && !(passed===false || st==='failed')) return false;
    if (statusSel==='pending' && st!=='pending') return false;
    if (statusSel==='ran' && !((scenario.total_tokens||0)>0 || (scenario.total_latency_seconds||0)>0)) return false;
    if (!filter) return true;
    const hay = JSON.stringify(scenario).toLowerCase();
    return hay.includes(filter);
  });

  rows.sort((a,b) => {
    const av=a.scenario[sortKey], bv=b.scenario[sortKey];
    if (typeof av==='string') return sortDir*String(av).localeCompare(String(bv));
    return sortDir*(((av||0)-(bv||0)));
  });

  const body = el('tbody');
  if (!rows.length){ body.innerHTML = '<tr><td colspan="9" class="empty">No scenarios match the filter.</td></tr>'; return; }

  body.innerHTML = rows.map(({scenario:s}, i) => {
    const rid = 'r'+i;
    const b = baseOf(s.scenario_id);
    const cell = (val, key, d=0, lowerIsBetter=true) =>
      `<td>${fmt(val,d)}${b ? deltaHTML(val, b[key], d, lowerIsBetter) : ''}</td>`;
    const main = `<tr class="main-row" data-toggle="${rid}">
      <td><span class="expand-btn" id="ind-${rid}">▸</span> ${esc(s.scenario_id)}</td>
      <td>${statusBadge(s.status, s.passed)}</td>
      ${cell(s.num_queries, 'num_queries', 0, true)}
      ${cell(s.attempts, 'attempts', 0, true)}
      ${cell(s.total_tokens, 'total_tokens', 0, true)}
      ${cell(s.llm_call_count, 'llm_call_count', 0, true)}
      ${cell(s.tool_call_count, 'tool_call_count', 0, true)}
      ${cell(s.total_latency_seconds, 'total_latency_seconds', 2, true)}
      ${cell(s.total_evaluation_latency_seconds, 'total_evaluation_latency_seconds', 2, true)}
    </tr>`;
    const detail = `<tr class="detail-row" id="${rid}" style="display:none"><td colspan="9">${renderScenarioDetail(s)}</td></tr>`;
    return main + detail;
  }).join('');

  body.querySelectorAll('tr.main-row').forEach(tr => tr.addEventListener('click', () => {
    const rid = tr.getAttribute('data-toggle');
    const row = el(rid);
    const ind = el('ind-'+rid);
    const open = row.style.display !== 'none';
    row.style.display = open ? 'none' : 'table-row';
    if (ind) ind.textContent = open ? '▸' : '▾';
  }));
}

function renderScenarioDetail(s){
  let html = '';
  if (s.description) html += `<div class="kv" style="margin:4px 0 10px">${esc(s.description)}</div>`;
  if (s.status_reason) html += `<div class="kv" style="margin:4px 0 10px"><b>reason:</b> ${esc(s.status_reason)}</div>`;
  const queries = s.queries || [];
  if (!queries.length) return html + '<div class="empty">No queries recorded (scenario pending).</div>';

  html += queries.map(q => {
    const m = q.metrics || {};
    const cls = q.passed===false ? 'qbad' : 'qok';
    const tools = (m.tool_calls||[]).length ? `tools: ${esc((m.tool_calls||[]).join(', '))}` : 'tools: none';
    let block = `<div class="q ${cls}">
      <div class="query-text">${esc(q.user_query)} ${statusBadge(q.status, q.passed)}</div>
      <div class="meta">
        <span>${esc((q.resource||{}).kind||'')} ${esc((q.resource||{}).name||'')} @ ${esc((q.resource||{}).namespace||'')}</span>
        <span>${fmt(m.total_tokens)} tok (${fmt(m.input_tokens)}/${fmt(m.output_tokens)})</span>
        <span>${fmt(m.latency_seconds,2)}s</span>
        <span>${fmt(m.llm_call_count)} LLM calls</span>
        <span>${esc(tools)}</span>
      </div>`;
    if (q.actual_response) block += `<div class="resp md">${renderMarkdown(q.actual_response)}</div>`;
    const exps = q.expectations || [];
    if (exps.length){
      block += '<div class="exp">' + exps.map(e => {
        const score = (e.score!==null && e.score!==undefined) ? Number(e.score) : null;
        const pct = score!==null ? Math.round(score*100) : 0;
        const ok = e.success===true;
        const color = e.success===true ? '#3fb950' : (e.success===false ? '#f85149' : '#8ea0c0');
        const scoreTxt = score!==null ? score.toFixed(2) : 'n/a';
        return `<div class="exp-item">
          <div class="exp-head">
            <span class="exp-name">${e.required?'★ ':''}${esc(e.name)} <span class="badge ${ok?'b-ok':(e.success===false?'b-bad':'b-neutral')}">${scoreTxt}</span></span>
            <span class="kv">threshold ${fmt(e.threshold,2)}</span>
          </div>
          ${e.statement?`<div class="kv" style="margin-top:6px">${esc(e.statement)}</div>`:''}
          <div class="bar"><span style="width:${pct}%;background:${color}"></span></div>
          ${e.reason?`<div class="exp-reason">${esc(e.reason)}</div>`:''}
        </div>`;
      }).join('') + '</div>';
    }
    block += '</div>';
    return block;
  }).join('');
  return html;
}

function initTableControls(){
  el('search').addEventListener('input', renderTable);
  el('statusFilter').addEventListener('change', renderTable);
  document.querySelectorAll('th[data-key]').forEach(th => th.addEventListener('click', () => {
    const k = th.getAttribute('data-key');
    if (sortKey===k) sortDir*=-1; else { sortKey=k; sortDir=-1; }
    renderTable();
  }));
}

function renderRunInfo(){
  const bits = [];
  if (run.model_name) bits.push('model <b>' + esc(run.model_name) + '</b>');
  if (run.generated_at) bits.push('generated ' + esc(run.generated_at));
  if (run.companion_api_url) bits.push(esc(run.companion_api_url));
  el('runinfo').innerHTML = bits.join(' · ');
  const bi = el('baselineinfo');
  if (bi){
    if (HAS_BASELINE){
      const bm = baseRun.model_name ? ` model <b>${esc(baseRun.model_name)}</b>` : '';
      bi.innerHTML = ` · baseline (${fmt(baseScenarios.length)} scenarios)${bm}`;
    } else {
      bi.innerHTML = ' · no baseline loaded';
    }
  }
  renderModelInfo();
  const note = el('cmpNote');
  if (note) note.textContent = HAS_BASELINE
    ? '— current vs baseline; ▲/▼ red = degraded, green = improved'
    : '— no baseline loaded';
}

function renderModelInfo(){
  const host = el('modelinfo');
  if (!host) return;
  const rows = [
    ['Main model', run.model_name, baseRun.model_name],
    ['Mini model', run.model_mini_name, baseRun.model_mini_name],
    ['Embedding model', run.embedding_model_name, baseRun.embedding_model_name],
    ['Companion API', run.companion_api_url, baseRun.companion_api_url],
    ['Max workers', run.max_workers, baseRun.max_workers],
    ['Scenario retries', run.scenario_retries, baseRun.scenario_retries],
    ['Generated at', run.generated_at, baseRun.generated_at],
  ];
  const val = (v) => (v===undefined||v===null||v==='') ? '<span class="kv">—</span>' : esc(v);
  const diffCls = (a,b) => (HAS_BASELINE && String(a??'')!==String(b??'')) ? ' class="delta bad"' : '';
  const body = rows.map(([label,cur,base]) =>
    `<tr><td class="kv">${label}</td><td>${val(cur)}</td>` +
    (HAS_BASELINE ? `<td><span${diffCls(cur,base)}>${val(base)}</span></td>` : '') +
    `</tr>`
  ).join('');
  host.innerHTML =
    `<table class="model-table"><thead><tr><th>Setting</th><th>Current</th>` +
    (HAS_BASELINE ? `<th>Baseline</th>` : '') +
    `</tr></thead><tbody>${body}</tbody></table>`;
}

renderCards();
renderRunInfo();
renderCharts();
initTableControls();
renderTable();
"""

_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Kyma Companion — Evaluation Report</title>
<script src="{chartjs_src}"></script>
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></script>
<style>{styles}</style>
</head>
<body>
<header>
  <h1>Kyma Companion — Evaluation Report</h1>
  <div class="sub">source: {source_name}<span id="baselineinfo"></span> · <span id="runinfo"></span></div>
</header>
<main>
  <section><h2>Summary</h2><div class="cards" id="cards"></div></section>

  <section><h2>Run &amp; model details</h2>
    <div class="chart-box" id="modelinfo"></div>
  </section>

  <section><h2>Tokens &amp; latency <span class="kv" id="cmpNote"></span></h2>
    <div class="grid">
      <div class="chart-box"><h3>Total tokens per scenario (current vs baseline)</h3><div class="chart-wrap tall"><canvas id="chTokens"></canvas></div></div>
      <div class="chart-box"><h3>Latency per scenario (current vs baseline)</h3><div class="chart-wrap tall"><canvas id="chLatency"></canvas></div></div>
    </div>
  </section>

  <section><h2>Calls &amp; distribution</h2>
    <div class="grid">
      <div class="chart-box"><h3>LLM calls per scenario (current vs baseline)</h3><div class="chart-wrap tall"><canvas id="chLlm"></canvas></div></div>
      <div class="chart-box"><h3>Tool calls per scenario (current vs baseline)</h3><div class="chart-wrap tall"><canvas id="chToolCalls"></canvas></div></div>
      <div class="chart-box"><h3>Total tokens vs latency (current vs baseline)</h3><div class="chart-wrap tall"><canvas id="chScatter"></canvas></div></div>
    </div>
  </section>

  <section><h2>Outcomes <span class="kv">(current run only)</span></h2>
    <div class="pie-row">
      <div class="chart-box"><h3>Scenario status</h3><div class="chart-wrap"><canvas id="chStatus"></canvas></div></div>
      <div class="chart-box"><h3>Query status</h3><div class="chart-wrap"><canvas id="chQueryStatus"></canvas></div></div>
      <div class="chart-box"><h3>Tool usage</h3><div class="chart-wrap"><canvas id="chTools"></canvas></div></div>
    </div>
  </section>

  <section><h2>Expectation scores</h2>
    <div class="chart-box"><h3>Score distribution <span id="scoresNote" class="kv"></span></h3>
      <div class="chart-wrap"><canvas id="chScores"></canvas></div>
    </div>
  </section>

  <section><h2>Scenarios &amp; responses</h2>
    <div class="controls">
      <input id="search" type="search" placeholder="Search scenarios, queries, responses…" />
      <select id="statusFilter">
        <option value="all">All statuses</option>
        <option value="ran">Ran only</option>
        <option value="passed">Passed</option>
        <option value="failed">Failed</option>
        <option value="pending">Pending</option>
      </select>
      <span class="kv">Click a row to expand responses &amp; expectation scores. Click headers to sort. Numbers show the delta vs baseline.</span>
    </div>
    <div class="chart-box" style="padding:6px 4px">
      <table>
        <thead><tr>
          <th data-key="scenario_id">Scenario</th>
          <th data-key="passed">Status</th>
          <th data-key="num_queries">Queries</th>
          <th data-key="attempts">Attempts</th>
          <th data-key="total_tokens">Tokens</th>
          <th data-key="llm_call_count">LLM</th>
          <th data-key="tool_call_count">Tools</th>
          <th data-key="total_latency_seconds">Latency (s)</th>
          <th data-key="total_evaluation_latency_seconds">Eval (s)</th>
        </tr></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  </section>
</main>
<footer>Rendered from {source_name} · Kyma Companion evaluation metrics</footer>
<script>window.__METRICS__ = {data_json};</script>
<script>window.__BASELINE__ = {baseline_json};</script>
<script>{script}</script>
</body>
</html>
"""


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Render metrics.json into an interactive HTML dashboard.")
    parser.add_argument("input", nargs="?", default="metrics.json", help="Path to metrics.json (default: metrics.json)")
    parser.add_argument("-o", "--output", help="Output HTML path (default: <input stem>_report.html)")
    parser.add_argument(
        "-b",
        "--baseline",
        help="Path to baseline metrics JSON to compare against (default: baseline_metrics.json next to input)",
    )
    parser.add_argument("--open", action="store_true", help="Open the generated report in the default browser")
    parser.add_argument("--chartjs-src", default=DEFAULT_CHARTJS_SRC, help="Chart.js script URL or local path")
    args = parser.parse_args()

    input_path = Path(args.input)
    report = load_report(input_path)
    output_path = Path(args.output) if args.output else input_path.with_name(f"{input_path.stem}_report.html")

    baseline_path = Path(args.baseline) if args.baseline else input_path.with_name("baseline_metrics.json")
    baseline = load_baseline(baseline_path)
    baseline_name = baseline_path.name if baseline else ""

    html = build_html(
        report,
        baseline,
        source_name=input_path.name,
        baseline_name=baseline_name,
        chartjs_src=args.chartjs_src,
    )
    output_path.write_text(html, encoding="utf-8")

    scenarios = report.get("scenarios", [])
    baseline_note = f", baseline {baseline_path.name}" if baseline else " (no baseline found)"
    print(f"Wrote {output_path} ({len(html):,} bytes, {len(scenarios)} scenarios{baseline_note}).")
    if args.open:
        webbrowser.open(output_path.resolve().as_uri())


if __name__ == "__main__":
    main()
