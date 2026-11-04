// 사용법: Overpass 응답을 osm.json으로 저장한 뒤 node tools/build-graph.js <이 폴더의 절대경로>
const fs = require("fs"); const dir = process.argv[2]; const { haversine } = require(dir + "/dijkstra.js");
const d = JSON.parse(fs.readFileSync("osm.json", "utf8"));
const pos = new Map(); d.elements.filter(e => e.type == "node").forEach(n => pos.set(n.id, [n.lat, n.lon]));
const H = 3.6, W = 12; // 5톤 윙바디 가정: 전고 3.6m, 총중량 12t
const speed = { motorway: 80, motorway_link: 40, trunk: 70, trunk_link: 40, primary: 50, primary_link: 35, secondary: 40, secondary_link: 30, tertiary: 35, tertiary_link: 30, unclassified: 25, residential: 20 };
const num = s => { const m = String(s || "").match(/[\d.]+/); return m ? parseFloat(m[0]) : null; };
let ways = d.elements.filter(e => e.type == "way"); let excluded = 0, oneways = 0;
ways = ways.filter(w => { const t = w.tags, h = num(t.maxheight), mw = num(t.maxweight);
  if ((h && h < H) || (mw && mw < W) || t.hgv === "no" || t.access === "no" || t.access === "private" || t.motor_vehicle === "no") { excluded++; return false; } return true; });
const use = new Map(); ways.forEach(w => w.nodes.forEach((n, i) => use.set(n, (use.get(n) || 0) + ((i == 0 || i == w.nodes.length - 1) ? 2 : 1))));
const raw = [];
ways.forEach(w => { const t = w.tags; let fw = true, bw = true; const o = t.oneway;
  if (o === "yes" || o === "1" || o === "true" || t.highway === "motorway" || t.junction === "roundabout") bw = false;
  if (o === "-1") { fw = false; bw = true; }
  if (o === "no") { fw = true; bw = true; }
  if (!(fw && bw)) oneways++;
  const v = (num(t.maxspeed) ? Math.min(num(t.maxspeed), speed[t.highway]) : speed[t.highway]) / 3.6;
  let start = 0;
  for (let i = 1; i < w.nodes.length; i++) if (use.get(w.nodes[i]) >= 2 || i == w.nodes.length - 1) {
    const seg = w.nodes.slice(start, i + 1);
    if (seg.every(n => pos.has(n)) && seg[0] !== seg[seg.length - 1]) { let m = 0; for (let k = 1; k < seg.length; k++) m += haversine(pos.get(seg[k - 1]), pos.get(seg[k])); raw.push({ a: seg[0], b: seg[seg.length - 1], seg, m, fs: fw ? m / v : 0, bs: bw ? m / v : 0 }); }
    start = i;
  } });
const fwd = new Map(), rev = new Map(); const add = (M, a, b) => { if (!M.has(a)) M.set(a, []); M.get(a).push(b); };
raw.forEach(e => { if (e.fs) { add(fwd, e.a, e.b); add(rev, e.b, e.a); } if (e.bs) { add(fwd, e.b, e.a); add(rev, e.a, e.b); } });
const reach = (M, s) => { const seen = new Set([s]), st = [s]; while (st.length) { const u = st.pop(); (M.get(u) || []).forEach(v => { if (!seen.has(v)) { seen.add(v); st.push(v); } }); } return seen; };
const sp = [37.25, 126.85]; let seed = null, bd = 1e9;
for (const k of fwd.keys()) { const p = pos.get(k), dd = (p[0] - sp[0]) ** 2 + (p[1] - sp[1]) ** 2; if (dd < bd && rev.has(k) && fwd.get(k).length > 1) { bd = dd; seed = k; } }
const F = reach(fwd, seed), B = reach(rev, seed), keep = new Set([...F].filter(x => B.has(x)));
const idx = new Map(), nodes = []; const r5 = x => Math.round(x * 1e5) / 1e5; const P = id => { const p = pos.get(id); return [r5(p[0]), r5(p[1])]; };
const nid = id => { if (!idx.has(id)) { idx.set(id, nodes.length); nodes.push(P(id)); } return idx.get(id); };
const edges = [], geoms = [];
raw.forEach(e => { if (keep.has(e.a) && keep.has(e.b)) { edges.push([nid(e.a), nid(e.b), Math.round(e.m), Math.round(e.fs * 10) / 10, Math.round(e.bs * 10) / 10]); geoms.push(e.seg.slice(1, -1).map(P)); } });
const meta = { source: "OpenStreetMap (Overpass API)", extractedAt: d.osm3s.timestamp_osm_base, bbox: [37.10, 126.70, 37.42, 126.97], vehicle: { heightM: H, grossT: W }, excludedWays: excluded, oneWayWays: oneways, speedsKmh: speed };
const g = { meta, nodes, edges, geoms };
fs.writeFileSync(dir + "/data/road-graph.js", "window.ROAD_GRAPH=" + JSON.stringify(g) + ";");
fs.writeFileSync("graph.json", JSON.stringify(g));
console.log({ nodes: nodes.length, edges: edges.length, excluded, oneways, kb: Math.round(fs.statSync(dir + "/data/road-graph.js").size / 1024) });
