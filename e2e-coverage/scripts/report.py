#!/usr/bin/env python3
"""
读取 utg.json + flows.json，生成交互式 HTML 报告。

用法:
  python report.py --utg utg.json --flows flows.json -o report.html
  python report.py --utg utg.json --flows flows.json --features features/ -o report.html
  python report.py --utg utg.json -o report.html   # 无 flows 也能生成（只有状态图）
"""

import html
import json
import re
import sys
from pathlib import Path


def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_feature_files(features_path: str) -> list[dict]:
    """Parse .feature files into structured scenario data."""
    p = Path(features_path)
    files = list(p.glob("*.feature")) if p.is_dir() else [p] if p.exists() else []
    scenarios = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        current_tag = None
        current_group = None
        scenario = None
        for line in text.splitlines():
            stripped = line.strip()
            # Detect group comments like: # ===... \n # Group Name (flows ...) \n # ===...
            group_match = re.match(r'^#\s+(.+?)\s*\(flows?\s', stripped)
            if group_match:
                current_group = group_match.group(1).strip()
                continue
            if stripped.startswith("@"):
                current_tag = stripped.lstrip("@").strip()
                continue
            if stripped.startswith("Scenario:"):
                if scenario:
                    scenarios.append(scenario)
                scenario = {
                    "name": stripped[len("Scenario:"):].strip(),
                    "tag": current_tag or "happy",
                    "group": current_group or "Other",
                    "steps": [],
                }
                current_tag = None
                continue
            if scenario and re.match(r'^(Given|When|Then|And|But)\s', stripped):
                scenario["steps"].append(stripped)
        if scenario:
            scenarios.append(scenario)
    return scenarios


def layout_nodes(utg: dict) -> tuple[list[dict], int]:
    """Returns (nodes, svg_width). Handles large graphs without overlap."""
    states = utg["states"]
    transitions = utg["transitions"]
    start = utg["start_state"]

    adj: dict[str, list[str]] = {}
    for t in transitions:
        adj.setdefault(t["from"], []).append(t["to"])

    layers: dict[int, list[str]] = {}
    visited = {}
    queue = [(start, 0)]
    visited[start] = 0
    while queue:
        node, depth = queue.pop(0)
        layers.setdefault(depth, []).append(node)
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                visited[neighbor] = depth + 1
                queue.append((neighbor, depth + 1))

    for sid in states:
        if sid not in visited:
            layers.setdefault(0, []).append(sid)

    # Split dense layers into sub-rows (max 5 per row)
    MAX_PER_ROW = 5
    expanded_layers: list[list[str]] = []
    for depth in sorted(layers.keys()):
        layer = layers[depth]
        for i in range(0, len(layer), MAX_PER_ROW):
            expanded_layers.append(layer[i:i + MAX_PER_ROW])

    # Build label map and compute node widths
    label_map: dict[str, str] = {}
    title_map: dict[str, str] = {}
    width_map: dict[str, int] = {}
    for sid, state in states.items():
        label = sid
        title = sid
        if isinstance(state, dict):
            title = state.get("window_title", sid)
            n = state.get("interactive_elements_count", 0)
            if isinstance(state.get("interactive_elements"), list):
                n = len(state["interactive_elements"])
            label = f"{title} ({n})" if title else sid
            title = f"{title} ({n} elements)" if title else sid
        if len(label) > 16:
            label = label[:14] + "…"
        label_map[sid] = label
        title_map[sid] = title
        width_map[sid] = max(110, len(label) * 7 + 30)

    # Layout with dynamic spacing
    y_gap = 100
    x_padding = 60
    nodes = []
    max_row_width = 0

    for row_idx, layer in enumerate(expanded_layers):
        # Compute total width needed for this row
        row_node_widths = [width_map.get(sid, 110) for sid in layer]
        x_gap = max(40, 170 - max(0, len(layer) - 3) * 20)  # tighter for wider rows
        row_width = sum(row_node_widths) + x_gap * (len(layer) - 1) if len(layer) > 1 else row_node_widths[0]
        max_row_width = max(max_row_width, row_width)

        start_x = x_padding + row_width // 2  # center anchor
        cursor_x = x_padding
        for i, sid in enumerate(layer):
            w = width_map.get(sid, 110)
            nodes.append({
                "id": sid,
                "x": cursor_x + w // 2,
                "y": 55 + row_idx * y_gap,
                "w": w,
                "h": 36,
                "label": label_map.get(sid, sid),
                "title": title_map.get(sid, sid),
            })
            cursor_x += w + x_gap

    svg_width = max(900, max_row_width + x_padding * 2 + 100)
    return nodes, svg_width


def build_edges(utg: dict) -> list[dict]:
    seen = set()
    edges = []
    for t in utg["transitions"]:
        key = (t["from"], t["to"])
        if key in seen:
            continue
        seen.add(key)
        label = t.get("action", "")
        if len(label) > 12:
            label = label[:10] + "…"
        edges.append({"from": t["from"], "to": t["to"], "label": label})
    return edges


def build_flows(flows_data: list[dict]) -> list[dict]:
    result = []
    for f in flows_data:
        result.append({
            "id": f.get("id", ""),
            "name": f.get("name", ""),
            "flow_path": f.get("flow_path", f.get("description", "")),
            "group": f.get("group", ""),
            "path": f.get("path", []),
            "edges": f.get("edges", []),
        })
    return result


def generate(utg, flows_data, output, app_name="", scenarios=None):
    if not app_name:
        first = next(iter(utg["states"].values()), {})
        app_name = first.get("app_name", first.get("window_title", "App"))

    nodes, svg_w = layout_nodes(utg)
    edges = build_edges(utg)
    flows = build_flows(flows_data) if flows_data else []
    svg_h = max(250, max((n["y"] for n in nodes), default=55) + 80)

    report = TEMPLATE
    report = report.replace("{{APP_NAME}}", html.escape(str(app_name)))

    def safe_json(obj):
        """Escape </script> in JSON to prevent breaking the HTML script block."""
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")

    report = report.replace("{{NODES}}", safe_json(nodes))
    report = report.replace("{{EDGES}}", safe_json(edges))
    report = report.replace("{{FLOWS}}", safe_json(flows))
    report = report.replace("{{SCENARIOS}}", safe_json(scenarios or []))
    report = report.replace("{{SVG_W}}", str(svg_w))
    report = report.replace("{{SVG_H}}", str(svg_h))
    report = report.replace("{{STATS}}", json.dumps(utg.get("stats", {}), ensure_ascii=False))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"Report saved to {output}")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>E2E Coverage — {{APP_NAME}}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f6f8;color:#333}
.header{background:#fff;border-bottom:1px solid #e5e7eb;padding:18px 30px}
.header h1{font-size:18px}
.header .sub{font-size:12px;color:#999;margin-top:2px}
.main{max-width:1060px;margin:0 auto;padding:20px}
.summary-bar{display:flex;gap:14px;margin-bottom:22px}
.summary-card{flex:1;background:#fff;border-radius:10px;padding:14px;border:1px solid #e5e7eb;text-align:center}
.summary-card .v{font-size:26px;font-weight:700}
.summary-card .l{font-size:11px;color:#888;margin-top:2px}
.sc-blue .v{color:#2563eb}.sc-green .v{color:#16a34a}.sc-orange .v{color:#f59e0b}.sc-red .v{color:#ef4444}.sc-gray .v{color:#9ca3af}
.graph-card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;margin-bottom:18px;overflow-x:auto}
.graph-title{font-size:13px;font-weight:600;color:#666;margin-bottom:10px}
.legend{display:flex;gap:14px;font-size:11px;color:#888;margin-bottom:12px;flex-wrap:wrap}
.legend span{display:flex;align-items:center;gap:4px}
.legend i{width:10px;height:10px;border-radius:2px;display:inline-block}
.legend .ls{width:18px;height:2px;display:inline-block;border-radius:1px}
svg.g text{user-select:none}
svg.g .ng{cursor:pointer}
svg.g .nr{transition:filter .2s,opacity .2s}
svg.g .nt{transition:opacity .2s}
svg.g .ep{fill:none;transition:stroke .2s,stroke-width .2s,opacity .2s}
svg.g .elb,svg.g .elt{transition:opacity .2s}
body.hl .ng.dim .nr{opacity:.15}body.hl .ng.dim .nt{opacity:.15}
body.hl .ep.dim{opacity:.08}body.hl .elb.dim{opacity:.08}body.hl .elt.dim{opacity:.08}
body.hl .ep.lit{stroke:#2563eb!important;stroke-width:2.5!important}
body.hl .ng.lit .nr{filter:drop-shadow(0 0 8px rgba(37,99,235,.45));stroke:#2563eb!important;stroke-width:2.5!important}
.flow-section{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:18px;margin-bottom:14px}
.flow-sec-title{font-size:14px;font-weight:600;margin-bottom:10px;display:flex;align-items:center;gap:8px}
.flow-sec-title .dot{width:8px;height:8px;border-radius:50%}
.ft{width:100%;border-collapse:collapse}
.ft th{text-align:left;font-size:11px;font-weight:600;color:#999;padding:5px 10px;border-bottom:1px solid #f0f0f0}
.ft td{padding:7px 10px;font-size:13px;border-bottom:1px solid #f8f8f8}
.ft tbody tr{cursor:pointer;transition:background .12s}
.ft tbody tr:hover{background:#f0f7ff}
.ft tbody tr.active{background:#eff6ff}
.badge{display:inline-block;padding:2px 10px;border-radius:10px;font-size:10px;font-weight:700}
.badge-happy{background:#dcfce7;color:#16a34a}
.badge-error{background:#fef2f2;color:#ef4444}
.badge-boundary{background:#fff7ed;color:#f59e0b}
.fp{font-size:12px;color:#888}
.tooltip{position:fixed;background:#1e293b;color:#fff;padding:8px 12px;border-radius:8px;font-size:12px;pointer-events:none;display:none;z-index:100;max-width:260px;line-height:1.5;box-shadow:0 4px 16px rgba(0,0,0,.2)}
/* Test Cases section */
.tc-section{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:18px;margin-bottom:14px}
.tc-title{font-size:14px;font-weight:600;margin-bottom:14px}
.tc-group{border:1px solid #e5e7eb;border-radius:8px;margin-bottom:10px;overflow:hidden}
.tc-group-header{padding:10px 14px;background:#f9fafb;cursor:pointer;display:flex;justify-content:space-between;align-items:center;font-weight:600;font-size:13px;user-select:none}
.tc-group-header:hover{background:#f0f4ff}
.tc-group-header .arrow{transition:transform .2s;font-size:10px;color:#999}
.tc-group-header .arrow.open{transform:rotate(90deg)}
.tc-group-header .gcount{font-size:11px;color:#999;font-weight:400;margin-left:8px}
.tc-group-body{display:none;border-top:1px solid #e5e7eb}
.tc-group-body.open{display:block}
.tc-item{padding:8px 14px;border-bottom:1px solid #f5f5f5;cursor:pointer;display:flex;align-items:center;gap:8px;font-size:13px}
.tc-item:last-child{border-bottom:none}
.tc-item:hover{background:#fafbff}
.tc-steps{display:none;padding:6px 14px 10px 36px;background:#f9fafb;font-size:12px;color:#555;line-height:1.8;border-bottom:1px solid #f0f0f0}
.tc-steps.open{display:block}
.tc-step{font-family:'SF Mono',Monaco,Consolas,monospace}
.tc-step-kw{color:#2563eb;font-weight:600}
</style>
</head>
<body>
<div class="header">
<h1>E2E Coverage Report — {{APP_NAME}}</h1>
<div class="sub">State graph + LLM-designed flows + BDD test cases · auto-generated</div>
</div>
<div class="main">
<div id="summary"></div>
<div class="graph-card">
<div class="graph-title">State Graph</div>
<div class="legend">
<span><i style="background:#16a34a"></i> State</span>
<span><span class="ls" style="background:#16a34a"></span> Transition</span>
<span><span class="ls" style="background:#2563eb"></span> Selected Flow</span>
</div>
<svg id="svg" class="g" viewBox="0 0 {{SVG_W}} {{SVG_H}}" style="width:100%;display:block"></svg>
</div>
<div id="tcs"></div>
<div id="fs"></div>
</div>
<div class="tooltip" id="tip"></div>
<script>
const C={pass:'#16a34a',hl:'#2563eb'};
const NS='http://www.w3.org/2000/svg';
const tip=document.getElementById('tip');
const NODES={{NODES}};
const EDGES={{EDGES}};
const FLOWS={{FLOWS}};
const SCENARIOS={{SCENARIOS}};
const STATS={{STATS}};
function renderSummary(){
const el=document.getElementById('summary');
const nH=SCENARIOS.filter(s=>s.tag==='happy').length;
const nE=SCENARIOS.filter(s=>s.tag==='error').length;
const nB=SCENARIOS.filter(s=>s.tag==='boundary').length;
const scCard=SCENARIOS.length?`
<div class="summary-card sc-green"><div class="v">${nH}</div><div class="l">Happy Cases</div></div>
<div class="summary-card sc-red"><div class="v">${nE}</div><div class="l">Error Cases</div></div>
<div class="summary-card sc-orange"><div class="v">${nB}</div><div class="l">Boundary Cases</div></div>`:'';
el.innerHTML=`<div class="summary-bar">
<div class="summary-card sc-blue"><div class="v">${NODES.length}</div><div class="l">States</div></div>
<div class="summary-card sc-blue"><div class="v">${EDGES.length}</div><div class="l">Transitions</div></div>
<div class="summary-card sc-blue"><div class="v">${FLOWS.length}</div><div class="l">Flows</div></div>
<div class="summary-card sc-green"><div class="v">${SCENARIOS.length}</div><div class="l">Test Cases</div></div>
${scCard}
<div class="summary-card sc-gray"><div class="v">${STATS.elapsed_seconds||'—'}s</div><div class="l">Explore Time</div></div>
</div>`;
}
function cb(p0,p1,p2,p3,t){const u=1-t;return u*u*u*p0+3*u*u*t*p1+3*u*t*t*p2+t*t*t*p3}
function bez(f,t){
const dx=t.x-f.x,dy=t.y-f.y,ax=Math.abs(dx),ay=Math.abs(dy);
let x1,y1,x2,y2;
if(ay<10){if(dx>0){x1=f.x+f.w/2;y1=f.y;x2=t.x-t.w/2;y2=t.y}else{x1=f.x-f.w/2;y1=f.y;x2=t.x+t.w/2;y2=t.y}}
else if(ax<10){if(dy>0){x1=f.x;y1=f.y+f.h/2;x2=t.x;y2=t.y-t.h/2}else{x1=f.x;y1=f.y-f.h/2;x2=t.x;y2=t.y+t.h/2}}
else{if(dy>0){x1=f.x;y1=f.y+f.h/2;x2=t.x;y2=t.y-t.h/2}else{x1=f.x-f.w/2;y1=f.y;x2=t.x-t.w/2;y2=t.y}}
let c1x,c1y,c2x,c2y;
if(ay<10){c1x=(x1+x2)/2;c1y=y1;c2x=(x1+x2)/2;c2y=y2}
else if(dy<0&&ax>10){const o=-50-ay*.2;c1x=x1+o;c1y=y1;c2x=x2+o;c2y=y2}
else{const s=Math.min(ay*.55,80);c1x=x1;c1y=y1+s;c2x=x2;c2y=y2-s}
return{d:`M ${x1} ${y1} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${x2} ${y2}`,mx:cb(x1,c1x,c2x,x2,.5),my:cb(y1,c1y,c2y,y2,.5)-2}
}
function drawGraph(){
const svg=document.getElementById('svg');
const nm={};NODES.forEach(n=>nm[n.id]=n);
const defs=document.createElementNS(NS,'defs');svg.appendChild(defs);
['pass','hl'].forEach(s=>{const m=document.createElementNS(NS,'marker');m.setAttribute('id','a-'+s);m.setAttribute('viewBox','0 0 8 6');m.setAttribute('refX',7);m.setAttribute('refY',3);m.setAttribute('markerWidth',5);m.setAttribute('markerHeight',4);m.setAttribute('orient','auto-start-reverse');const p=document.createElementNS(NS,'path');p.setAttribute('d','M 0 0.5 L 7 3 L 0 5.5 z');p.setAttribute('fill',C[s]);m.appendChild(p);defs.appendChild(m)});
EDGES.forEach(e=>{const f=nm[e.from],t=nm[e.to];if(!f||!t)return;const p=bez(f,t);const eid=e.from+'__'+e.to;
const pa=document.createElementNS(NS,'path');pa.setAttribute('d',p.d);pa.setAttribute('stroke',C.pass);pa.setAttribute('stroke-width',1.5);pa.setAttribute('fill','none');pa.setAttribute('marker-end','url(#a-pass)');pa.classList.add('ep');pa.dataset.eid=eid;svg.appendChild(pa);
const lw=e.label.length*6+14;const bg=document.createElementNS(NS,'rect');bg.setAttribute('x',p.mx-lw/2);bg.setAttribute('y',p.my-8);bg.setAttribute('width',lw);bg.setAttribute('height',16);bg.setAttribute('rx',8);bg.setAttribute('fill','#fff');bg.setAttribute('stroke','#e5e7eb');bg.setAttribute('stroke-width',.5);bg.classList.add('elb');bg.dataset.eid=eid;svg.appendChild(bg);
const lt=document.createElementNS(NS,'text');lt.setAttribute('x',p.mx);lt.setAttribute('y',p.my+3);lt.setAttribute('text-anchor','middle');lt.setAttribute('font-size','10');lt.setAttribute('fill','#888');lt.textContent=e.label;lt.classList.add('elt');lt.dataset.eid=eid;svg.appendChild(lt)});
NODES.forEach(n=>{const g=document.createElementNS(NS,'g');g.classList.add('ng');g.dataset.nid=n.id;
const sh=document.createElementNS(NS,'rect');sh.setAttribute('x',n.x-n.w/2+2);sh.setAttribute('y',n.y-n.h/2+2);sh.setAttribute('width',n.w);sh.setAttribute('height',n.h);sh.setAttribute('rx',10);sh.setAttribute('fill','rgba(0,0,0,.04)');g.appendChild(sh);
const r=document.createElementNS(NS,'rect');r.setAttribute('x',n.x-n.w/2);r.setAttribute('y',n.y-n.h/2);r.setAttribute('width',n.w);r.setAttribute('height',n.h);r.setAttribute('rx',10);r.setAttribute('fill','#f0fdf4');r.setAttribute('stroke',C.pass);r.setAttribute('stroke-width',1.8);r.classList.add('nr');g.appendChild(r);
const tx=document.createElementNS(NS,'text');tx.setAttribute('x',n.x);tx.setAttribute('y',n.y+1);tx.setAttribute('text-anchor','middle');tx.setAttribute('dominant-baseline','middle');tx.setAttribute('font-size','12');tx.setAttribute('font-weight','600');tx.setAttribute('fill','#333');tx.textContent=n.label;tx.classList.add('nt');g.appendChild(tx);
g.addEventListener('mouseenter',ev=>{const fl=FLOWS.filter(f=>f.path.includes(n.id));const ls=fl.map(f=>'• '+f.name);tip.innerHTML=`<b>${n.title||n.label}</b><br>${n.id}${ls.length?'<br><br>Flows:<br>'+ls.join('<br>'):''}`;tip.style.display='block'});
g.addEventListener('mouseleave',()=>tip.style.display='none');
g.addEventListener('mousemove',ev=>{tip.style.left=(ev.clientX+14)+'px';tip.style.top=(ev.clientY-10)+'px'});
svg.appendChild(g)})
}
let af=null;
function drawFS(){
const el=document.getElementById('fs');
const gMap={};
FLOWS.forEach((f,i)=>{const g=f.group||'Other';(gMap[g]=gMap[g]||[]).push({...f,idx:i})});
const gNames=Object.keys(gMap);
let h=`<div class="flow-section"><div class="flow-sec-title">Flows (${FLOWS.length})</div>`;
gNames.forEach((g,gi)=>{
const items=gMap[g];
h+=`<div class="tc-group"><div class="tc-group-header" onclick="togG(this)"><span>${esc(g)}<span class="gcount">${items.length} flows</span></span><span class="arrow">&#9654;</span></div><div class="tc-group-body">`;
h+=`<table class="ft"><thead><tr><th style="width:50px">#</th><th>Flow</th><th>Path</th></tr></thead><tbody>`;
items.forEach(f=>{h+=`<tr data-fid="${f.id}" onmouseenter="hlF('${f.id}')" onmouseleave="clr()" onclick="tog('${f.id}')"><td>${f.idx+1}</td><td style="font-weight:600">${esc(f.name)}</td><td class="fp">${esc(f.flow_path)}</td></tr>`});
h+=`</tbody></table></div></div>`;
});
h+=`</div>`;
el.innerHTML=h}
function hlF(id){if(af)return;aH(id)}
function clr(){if(af)return;rH()}
function tog(id){if(af===id){af=null;rH();document.querySelectorAll('.ft tr.active').forEach(r=>r.classList.remove('active'))}else{af=id;document.querySelectorAll('.ft tr.active').forEach(r=>r.classList.remove('active'));document.querySelector(`tr[data-fid="${id}"]`)?.classList.add('active');aH(id)}}
function aH(id){const fl=FLOWS.find(f=>f.id===id);if(!fl)return;document.body.classList.add('hl');const svg=document.getElementById('svg');const pn=new Set(fl.path),pe=new Set(fl.edges.map(([a,b])=>a+'__'+b));svg.querySelectorAll('.ng').forEach(g=>{g.classList.toggle('lit',pn.has(g.dataset.nid));g.classList.toggle('dim',!pn.has(g.dataset.nid))});svg.querySelectorAll('.ep').forEach(p=>{p.classList.toggle('lit',pe.has(p.dataset.eid));p.classList.toggle('dim',!pe.has(p.dataset.eid))});svg.querySelectorAll('.elb,.elt').forEach(el=>{el.classList.toggle('dim',!pe.has(el.dataset.eid))})}
function rH(){document.body.classList.remove('hl');document.getElementById('svg').querySelectorAll('.lit,.dim').forEach(el=>el.classList.remove('lit','dim'))}

// Test Cases
function drawTC(){
if(!SCENARIOS.length)return;
const el=document.getElementById('tcs');
const groups={};
SCENARIOS.forEach(s=>{(groups[s.group]=groups[s.group]||[]).push(s)});
const gNames=Object.keys(groups);
let h=`<div class="tc-section"><div class="tc-title">Test Cases (${SCENARIOS.length})</div>`;
gNames.forEach((g,gi)=>{
const items=groups[g];
const nH=items.filter(s=>s.tag==='happy').length;
const nE=items.filter(s=>s.tag==='error').length;
const nB=items.filter(s=>s.tag==='boundary').length;
const counts=[];
if(nH)counts.push(nH+' happy');
if(nE)counts.push(nE+' error');
if(nB)counts.push(nB+' boundary');
h+=`<div class="tc-group"><div class="tc-group-header" onclick="togG(this)"><span>${g}<span class="gcount">${items.length} cases (${counts.join(', ')})</span></span><span class="arrow">&#9654;</span></div><div class="tc-group-body">`;
items.forEach((s,si)=>{
const sid='tc_'+gi+'_'+si;
const bc='badge-'+s.tag;
h+=`<div class="tc-item" onclick="togS('${sid}')"><span class="badge ${bc}">@${s.tag}</span> ${esc(s.name)}</div>`;
h+=`<div class="tc-steps" id="${sid}">`;
s.steps.forEach(st=>{
const m=st.match(/^(Given|When|Then|And|But)\s+(.*)/);
if(m)h+=`<div class="tc-step"><span class="tc-step-kw">${m[1]}</span> ${esc(m[2])}</div>`;
else h+=`<div class="tc-step">${esc(st)}</div>`;
});
h+=`</div>`;
});
h+=`</div></div>`;
});
h+=`</div>`;
el.innerHTML=h;
}
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function togG(el){el.querySelector('.arrow').classList.toggle('open');el.nextElementSibling.classList.toggle('open')}
function togS(id){document.getElementById(id).classList.toggle('open')}

renderSummary();drawGraph();drawFS();drawTC();
</script>
</body>
</html>
"""


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate E2E coverage HTML report")
    parser.add_argument("--utg", required=True, help="Path to utg.json")
    parser.add_argument("--flows", help="Path to flows.json (optional)")
    parser.add_argument("--features", help="Path to .feature file or features/ directory")
    parser.add_argument("-o", "--output", default="report.html", help="Output HTML path")
    parser.add_argument("--app-name", default="", help="App name for title")
    args = parser.parse_args()

    utg = load_json(args.utg)
    flows = load_json(args.flows) if args.flows else None
    scenarios = parse_feature_files(args.features) if args.features else None
    generate(utg, flows, Path(args.output), app_name=args.app_name, scenarios=scenarios)


if __name__ == "__main__":
    main()
