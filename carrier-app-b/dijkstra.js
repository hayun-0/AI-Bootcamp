/* 도로 그래프 위 다익스트라. 브라우저와 Node에서 같은 코드로 동작한다.
   edges[i] = [u, v, 미터, 정방향 초, 역방향 초(0이면 일방통행)], geoms[i] = 중간 형상점 */
(function (root) {
  function MinHeap() { this.k = []; this.v = []; }
  MinHeap.prototype.push = function (key, val) {
    var k = this.k, v = this.v, i = k.length; k.push(key); v.push(val);
    while (i > 0) { var p = (i - 1) >> 1; if (k[p] <= key) break; k[i] = k[p]; v[i] = v[p]; i = p; }
    k[i] = key; v[i] = val;
  };
  MinHeap.prototype.pop = function () {
    var k = this.k, v = this.v, topV = v[0], topK = k[0], lastK = k.pop(), lastV = v.pop(), n = k.length;
    if (n > 0) {
      var i = 0;
      while (true) {
        var l = 2 * i + 1, r = l + 1, c = l;
        if (l >= n) break;
        if (r < n && k[r] < k[l]) c = r;
        if (k[c] >= lastK) break;
        k[i] = k[c]; v[i] = v[c]; i = c;
      }
      k[i] = lastK; v[i] = lastV;
    }
    return { key: topK, val: topV };
  };
  MinHeap.prototype.size = function () { return this.k.length; };

  function haversine(a, b) {
    var R = 6371000, t = Math.PI / 180, dLat = (b[0] - a[0]) * t, dLon = (b[1] - a[1]) * t;
    var s = Math.sin(dLat / 2), c = Math.sin(dLon / 2);
    var h = s * s + Math.cos(a[0] * t) * Math.cos(b[0] * t) * c * c;
    return 2 * R * Math.asin(Math.sqrt(h));
  }
  function now() { return (typeof performance !== "undefined" ? performance : Date).now(); }

  function createRouter(graph) {
    var N = graph.nodes.length, adj = [], i;
    for (i = 0; i < N; i++) adj.push([]);
    graph.edges.forEach(function (e, idx) {
      if (e[3] > 0) adj[e[0]].push([e[1], e[3], e[2], idx, 0]);
      if (e[4] > 0) adj[e[1]].push([e[0], e[4], e[2], idx, 1]);
    });
    function nearest(lat, lon) {
      var best = -1, bd = Infinity, cos = Math.cos(lat * Math.PI / 180);
      for (var i = 0; i < N; i++) {
        var n = graph.nodes[i], dy = n[0] - lat, dx = (n[1] - lon) * cos, d = dx * dx + dy * dy;
        if (d < bd) { bd = d; best = i; }
      }
      return { node: best, snapMeters: Math.round(haversine([lat, lon], graph.nodes[best])) };
    }
    function shortest(s, t) {
      var t0 = now();
      var dist = new Float64Array(N).fill(Infinity), prevN = new Int32Array(N).fill(-1), prevE = new Array(N), done = new Uint8Array(N);
      var h = new MinHeap(), settled = 0; dist[s] = 0; h.push(0, s);
      while (h.size()) {
        var top = h.pop(), u = top.val;
        if (done[u]) continue;
        done[u] = 1; settled++;
        if (u === t) break;
        var list = adj[u];
        for (var j = 0; j < list.length; j++) {
          var a = list[j], nd = top.key + a[1];
          if (nd < dist[a[0]]) { dist[a[0]] = nd; prevN[a[0]] = u; prevE[a[0]] = a; h.push(nd, a[0]); }
        }
      }
      var ms = now() - t0;
      if (dist[t] === Infinity) return null;
      var chain = [], c = t; while (c !== s) { chain.push(prevE[c]); c = prevN[c]; }
      chain.reverse();
      var coords = [graph.nodes[s]], meters = 0;
      chain.forEach(function (a) {
        meters += a[2];
        var g = graph.geoms[a[3]].slice(); if (a[4]) g.reverse();
        for (var k = 0; k < g.length; k++) coords.push(g[k]);
        coords.push(graph.nodes[a[0]]);
      });
      return { coords: coords, meters: meters, seconds: dist[t], settled: settled, totalNodes: N, computeMs: ms, hops: chain.length };
    }
    function route(from, to) {
      var a = nearest(from[0], from[1]), b = nearest(to[0], to[1]);
      var r = shortest(a.node, b.node);
      if (r) { r.snapFrom = a.snapMeters; r.snapTo = b.snapMeters; }
      return r;
    }
    return { route: route, shortest: shortest, nearest: nearest, adj: adj, size: N };
  }
  var api = { createRouter: createRouter, haversine: haversine };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.Dijkstra = api;
})(this);
