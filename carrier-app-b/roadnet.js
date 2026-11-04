/* Overpass 응답(OSM JSON)을 다익스트라용 그래프로 바꾼다. 브라우저와 Node에서 같은 코드로 동작한다. */
(function (root) {
  var SPEED = { motorway: 80, motorway_link: 40, trunk: 70, trunk_link: 40, primary: 50, primary_link: 35, secondary: 40, secondary_link: 30, tertiary: 35, tertiary_link: 30, unclassified: 25, residential: 20 };
  var HV = root.Dijkstra ? root.Dijkstra.haversine : require("./dijkstra.js").haversine;
  function num(s) { var m = String(s || "").match(/[\d.]+/); return m ? parseFloat(m[0]) : null; }
  function r5(x) { return Math.round(x * 1e5) / 1e5; }

  function build(osm, vehicle) {
    var H = vehicle.heightM, W = vehicle.grossT, pos = new Map(), excluded = 0;
    osm.elements.forEach(function (e) { if (e.type === "node") pos.set(e.id, [e.lat, e.lon]); });
    var ways = osm.elements.filter(function (e) {
      if (e.type !== "way" || !e.tags) return false;
      var t = e.tags, h = num(t.maxheight), mw = num(t.maxweight);
      if ((h && h < H) || (mw && mw < W) || t.hgv === "no" || t.access === "no" || t.access === "private" || t.motor_vehicle === "no") { excluded++; return false; }
      return true;
    });
    var use = new Map();
    ways.forEach(function (w) { w.nodes.forEach(function (n, i) { use.set(n, (use.get(n) || 0) + ((i === 0 || i === w.nodes.length - 1) ? 2 : 1)); }); });
    var raw = [];
    ways.forEach(function (w) {
      var t = w.tags, fw = true, bw = true, o = t.oneway;
      if (o === "yes" || o === "1" || o === "true" || t.highway === "motorway" || t.junction === "roundabout") bw = false;
      if (o === "-1") { fw = false; bw = true; }
      if (o === "no") { fw = true; bw = true; }
      var cls = SPEED[t.highway] || 20, ms = num(t.maxspeed), v = (ms ? Math.min(ms, cls) : cls) / 3.6, start = 0;
      for (var i = 1; i < w.nodes.length; i++) {
        if (use.get(w.nodes[i]) >= 2 || i === w.nodes.length - 1) {
          var seg = w.nodes.slice(start, i + 1), ok = seg.every(function (n) { return pos.has(n); });
          if (ok && seg[0] !== seg[seg.length - 1]) {
            var m = 0; for (var k = 1; k < seg.length; k++) m += HV(pos.get(seg[k - 1]), pos.get(seg[k]));
            raw.push({ a: seg[0], b: seg[seg.length - 1], seg: seg, m: m, fs: fw ? m / v : 0, bs: bw ? m / v : 0 });
          }
          start = i;
        }
      }
    });
    /* 양방향으로 오갈 수 있는 도로망만 남겨 끊긴 도로에 좌표가 붙지 않게 한다 */
    var fwd = new Map(), rev = new Map();
    function add(M, a, b) { if (!M.has(a)) M.set(a, []); M.get(a).push(b); }
    raw.forEach(function (e) { if (e.fs) { add(fwd, e.a, e.b); add(rev, e.b, e.a); } if (e.bs) { add(fwd, e.b, e.a); add(rev, e.a, e.b); } });
    /* 코사라주 알고리즘으로 가장 큰 강연결 요소를 찾는다 */
    var seen = new Set(), order = [];
    fwd.forEach(function (_, s) {
      if (seen.has(s)) return;
      seen.add(s);
      var st = [[s, 0]];
      while (st.length) {
        var top = st[st.length - 1], list = fwd.get(top[0]) || [];
        if (top[1] < list.length) { var nx = list[top[1]++]; if (!seen.has(nx)) { seen.add(nx); st.push([nx, 0]); } }
        else { order.push(top[0]); st.pop(); }
      }
    });
    var assigned = new Set(), best = null;
    for (var oi = order.length - 1; oi >= 0; oi--) {
      if (assigned.has(order[oi])) continue;
      var comp = new Set([order[oi]]), stack = [order[oi]]; assigned.add(order[oi]);
      while (stack.length) { (rev.get(stack.pop()) || []).forEach(function (v) { if (!assigned.has(v)) { assigned.add(v); comp.add(v); stack.push(v); } }); }
      if (!best || comp.size > best.size) best = comp;
    }
    if (!best || best.size < 2) return null;
    var idx = new Map(), nodes = [], edges = [], geoms = [];
    function P(id) { var p = pos.get(id); return [r5(p[0]), r5(p[1])]; }
    function nid(id) { if (!idx.has(id)) { idx.set(id, nodes.length); nodes.push(P(id)); } return idx.get(id); }
    raw.forEach(function (e) {
      if (best.has(e.a) && best.has(e.b)) {
        edges.push([nid(e.a), nid(e.b), Math.round(e.m), Math.round(e.fs * 10) / 10, Math.round(e.bs * 10) / 10]);
        geoms.push(e.seg.slice(1, -1).map(P));
      }
    });
    return { nodes: nodes, edges: edges, geoms: geoms, meta: { excludedWays: excluded } };
  }

  /* 두 좌표를 감싸는 영역의 도로 조회문. 먼 구간은 큰 도로만 받아 응답을 줄인다 */
  function query(a, b, directKm) {
    var cls = directKm <= 30 ? "motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified|residential" : "motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link";
    var mLat = Math.max(directKm * 0.3 / 111, 0.04), mLon = Math.max(directKm * 0.3 / 88, 0.05);
    var bb = [Math.min(a[0], b[0]) - mLat, Math.min(a[1], b[1]) - mLon, Math.max(a[0], b[0]) + mLat, Math.max(a[1], b[1]) + mLon].map(function (x) { return x.toFixed(4); }).join(",");
    return '[out:json][timeout:60];way["highway"~"^(' + cls + ')$"](' + bb + ");out body;>;out skel qt;";
  }
  var api = { build: build, query: query };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.RoadNet = api;
})(this);
