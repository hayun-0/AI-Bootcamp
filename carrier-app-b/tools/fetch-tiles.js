// 시연용 소량 타일을 내려받아 data/tiles.js로 묶는다. OSM 타일 사용 정책을 지키고 범위를 넓히지 말 것.
// 사용법: node tools/fetch-tiles.js <이 폴더의 절대경로>
const fs = require("fs"), path = require("path"), https = require("https"); const out = "tiles";
const W = [36.85, 126.35, 37.65, 127.35], M = [37.0, 126.6, 37.52, 127.07];
const lon2x = (l, z) => Math.floor((l + 180) / 360 * 2 ** z);
const lat2y = (a, z) => { const r = a * Math.PI / 180; return Math.floor((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * 2 ** z); };
const list = []; for (const [z, bb] of [[10, W], [11, W], [12, M], [13, M]]) for (let x = lon2x(bb[1], z); x <= lon2x(bb[3], z); x++) for (let y = lat2y(bb[2], z); y <= lat2y(bb[0], z); y++) list.push([z, x, y]);
const get = (z, x, y) => new Promise((res, rej) => { https.get({ host: "tile.openstreetmap.org", path: "/" + z + "/" + x + "/" + y + ".png", headers: { "User-Agent": "InnovationChallenger2026-prototype/0.1 (student project)", "Referer": "http://localhost/" } }, r => { if (r.statusCode !== 200) { r.resume(); return rej(new Error("HTTP " + r.statusCode)); } const b = []; r.on("data", c => b.push(c)); r.on("end", () => res(Buffer.concat(b))); }).on("error", rej); });
(async () => { let n = 0, fail = 0; for (const [z, x, y] of list) { const f = path.join(out, "" + z, "" + x, y + ".png"); if (fs.existsSync(f)) continue; fs.mkdirSync(path.dirname(f), { recursive: true }); try { fs.writeFileSync(f, await get(z, x, y)); n++; } catch (e) { fail++; console.log("fail", z, x, y, e.message); } await new Promise(r => setTimeout(r, 400)); }
  const T = {}; for (const [z, x, y] of list) { const f = path.join(out, "" + z, "" + x, y + ".png"); if (fs.existsSync(f)) T[z + "/" + x + "/" + y] = "data:image/png;base64," + fs.readFileSync(f).toString("base64"); }
  fs.writeFileSync(process.argv[2] + "/data/tiles.js", "window.TILES=" + JSON.stringify(T) + ";");
  console.log("new", n, "fail", fail, "bundled", Object.keys(T).length, "MB", (fs.statSync(process.argv[2] + "/data/tiles.js").size / 1048576).toFixed(1)); })();
