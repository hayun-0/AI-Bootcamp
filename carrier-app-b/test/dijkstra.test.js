// 실행: node test/dijkstra.test.js
// 내장 도로 그래프에서 다익스트라 결과를 독립 구현인 벨만-포드와 비교한다.
const fs = require("fs"), path = require("path"), assert = require("assert");
const { createRouter } = require("../dijkstra.js");
const raw = fs.readFileSync(path.join(__dirname, "../data/road-graph.js"), "utf8");
const graph = JSON.parse(raw.slice(raw.indexOf("{"), raw.lastIndexOf("}") + 1));
const R = createRouter(graph);
function bellmanFord(s) {
  const d = new Float64Array(R.size).fill(Infinity); d[s] = 0;
  const E = []; R.adj.forEach((l, u) => l.forEach(a => E.push([u, a[0], a[1]])));
  for (let it = 0; it < R.size; it++) { let ch = false; for (const [u, v, w] of E) if (d[u] + w < d[v]) { d[v] = d[u] + w; ch = true; } if (!ch) break; }
  return d;
}
const cases = [["안산 반월 → 화성 향남", [37.3055, 126.79], [37.1235, 126.9105]], ["안산 성곡 → 군포 당정", [37.296, 126.762], [37.3485, 126.937]], ["시흥 정왕 → 인천 남동", [37.343, 126.73], [37.405, 126.709]]];
for (const [name, a, b] of cases) {
  const r = R.route(a, b), s = R.nearest(a[0], a[1]).node, t = R.nearest(b[0], b[1]).node;
  assert.ok(Math.abs(bellmanFord(s)[t] - r.seconds) < 0.01, name);
  console.log("통과", name, (r.meters / 1000).toFixed(1) + "km", Math.round(r.seconds / 60) + "분");
}
