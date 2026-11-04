/* 운송 파트너 앱 B안(오더 보드형). 운임과 업체명은 예시이고, 거리와 시간은 도로 그래프에서 계산한다. */
(function () {
  var router = Dijkstra.createRouter(window.ROAD_GRAPH);
  var BOUNDS = [[37.10, 126.70], [37.42, 126.97]];
  var TILE_BOUNDS = [[36.85, 126.35], [37.65, 127.35]], LIVE = false;
  var EMPTY_TILE = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";
  var DataTiles = L.TileLayer.extend({ getTileUrl: function (c) { var k = this._getZoomForUrl() + "/" + c.x + "/" + c.y; return window.TILES[k] || (LIVE ? "https://tile.openstreetmap.org/" + k + ".png" : EMPTY_TILE); } });
  var DEPOT = { name: "우리 차고지 · 안산", at: [37.3045, 126.812] };
  var GB = window.ROAD_GRAPH.meta.bbox;
  function inGraph(p) { return p[0] >= GB[0] && p[0] <= GB[2] && p[1] >= GB[1] && p[1] <= GB[3]; }
  var ICON = {
    pin: '<path d="M12 22s7-7.5 7-12a7 7 0 0 0-14 0c0 4.5 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/>',
    bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
    truck: '<path d="M1 3h15v13H1z"/><path d="M16 8h4l3 3v5h-7z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
    home: '<path d="M3 11 12 3l9 8"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/>',
    won: '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="3"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
    back: '<path d="m15 6-6 6 6 6"/>', next: '<path d="m9 6 6 6-6 6"/>',
    phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.2a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
    qr: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><path d="M14 14h3v3h-3zM21 14v3M14 21h7"/>',
    check: '<path d="M20 6 9 17l-5-5"/>', play: '<path d="M8 5v14l11-7z" fill="currentColor"/>',
    map: '<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3z"/><path d="M9 3v15M15 6v15"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    nav: '<path d="m3 11 18-8-8 18-2-8z"/>',
    locate: '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>'
  };
  function ic(k, s) { s = s || 20; return '<svg aria-hidden="true" width="' + s + '" height="' + s + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + ICON[k] + "</svg>"; }
  function won(n) { return n.toLocaleString("ko-KR") + "원"; }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;"); }

  var ORDERS = [
    { id: 1, from: "안산 반월공단", to: "화성 향남", shipper: "한빛플라스틱", consignee: "그린순환자원", stops: [[37.3055, 126.79], [37.1235, 126.9105]], fare: 97000, base: 82000, premium: 10000, wait: 5000, item: "폐합성수지 PP", bags: 18, ton: 3.2, when: "오늘 14:00 당상", grade: "A", tags: ["인계서 자동", "독차"], pay: "익일 정산", rating: 4.8, cond: "지게차 있음", window: "14:00 ~ 16:00 상차", dropNote: "18:00까지 하차 · 계량대 있음" },
    { id: 2, from: "시흥 정왕", to: "인천 남동", via: "안산 반월 경유", shipper: "대성금속", consignee: "남동리사이클", stops: [[37.343, 126.73], [37.3055, 126.79], [37.405, 126.709]], fare: 143000, base: 112000, premium: 15000, wait: 16000, item: "고철", bags: 26, ton: 4.6, when: "내일 09:00 내착", grade: "A", tags: ["묶음 2곳", "인계서 자동"], pay: "지급일 확정", rating: 4.6, cond: "지게차 있음", window: "07:00 ~ 08:30 상차", dropNote: "09:00까지 하차" },
    { id: 3, from: "안산 성곡동", to: "군포 당정", shipper: "성곡자원", consignee: "당정제지원료", stops: [[37.296, 126.762], [37.3485, 126.937]], fare: 58000, base: 50000, premium: 3000, wait: 5000, item: "폐지 골판지", bags: 10, ton: 1.1, when: "오늘 16:30 당상", grade: "B", tags: ["혼적 가능"], pay: "익일 정산", rating: 4.3, cond: "수작업 상차", window: "16:30 ~ 17:30 상차", dropNote: "19:00까지 하차" },
    { id: 4, from: "화성 팔탄", to: "시흥 정왕", shipper: "팔탄알루미늄", consignee: "정왕비철", stops: [[37.166, 126.872], [37.343, 126.73]], fare: 112000, base: 92000, premium: 10000, wait: 10000, item: "비철 알루미늄", bags: 14, ton: 2.4, when: "11.05 (목) 10:00", grade: "A", tags: ["인계서 자동", "정기 운반"], pay: "월 4회 고정", rating: 4.9, cond: "지게차 있음", window: "10:00 ~ 11:00 상차", dropNote: "15:00까지 하차" },
    { id: 5, from: "안산 원시동", to: "화성 남양", shipper: "원시산업", consignee: "남양재생", stops: [[37.312, 126.77], [37.21, 126.82]], fare: 42000, base: 38000, premium: 0, wait: 4000, item: "폐비닐 압축", bags: 8, ton: 0.9, when: "오늘 17:00 당상", grade: "C", tags: ["혼적 가능"], pay: "익일 정산", rating: 4.1, cond: "수작업 상차", window: "17:00 ~ 18:00 상차", dropNote: "20:00까지 하차" }
  ];
  /* 차고지에서 첫 상차지까지(공차), 상차지부터 마지막 하차지까지(적재)를 각각 다익스트라로 계산한다 */
  ORDERS.forEach(function (o) {
    o.empty = router.route(DEPOT.at, o.stops[0]);
    o.legs = [];
    for (var i = 0; i + 1 < o.stops.length; i++) o.legs.push(router.route(o.stops[i], o.stops[i + 1]));
    o.km = o.legs.reduce(function (a, l) { return a + l.meters; }, 0) / 1000;
    o.min = Math.round(o.legs.reduce(function (a, l) { return a + l.seconds; }, 0) / 60);
    o.emptyKm = o.empty.meters / 1000; o.emptyMin = Math.round(o.empty.seconds / 60);
    o.perKm = Math.round(o.fare / (o.km + o.emptyKm));
    o.line = o.legs.reduce(function (a, l) { return a.concat(l.coords); }, []);
  });
  function km1(x) { return x.toFixed(1) + "km"; }
  function byId(id) { return ORDERS.filter(function (o) { return o.id === id; })[0]; }

  var LEDGER = [
    { d: "11.03 (화)", n: "안산 반월 → 화성 향남", v: 97000, s: "정산 예정", bundle: false },
    { d: "11.03 (화)", n: "안산 원시 → 시흥 정왕", v: 87000, s: "정산 예정", bundle: true },
    { d: "11.02 (월)", n: "안산 성곡 → 군포 당정", v: 58000, s: "정산 예정", bundle: false },
    { d: "10.31 (토)", n: "화성 팔탄 → 시흥 정왕", v: 112000, s: "정산 예정", bundle: false },
    { d: "10.30 (금)", n: "안산 반월 → 군포 당정", v: 46000, s: "정산 완료", bundle: false },
    { d: "10.29 (목)", n: "시흥 정왕 → 인천 남동", v: 124000, s: "정산 완료", bundle: true },
    { d: "10.28 (수)", n: "안산 원시 → 화성 남양", v: 88000, s: "정산 완료", bundle: true }
  ];
  var WEEK_TOTAL = LEDGER.reduce(function (a, l) { return a + l.v; }, 0);
  var PENDING = LEDGER.filter(function (l) { return l.s === "정산 예정"; }).reduce(function (a, l) { return a + l.v; }, 0);
  var STAGES = ["이동", "상차·검수", "운송", "하차·계량", "완료"];
  var S = { s: "home", online: false, id: 1, sort: "fare", fit: true, q: "", bmap: false, cd: 45, trip: { id: 1, stage: 1, scanned: 12 }, toast: "" };
  var phone = document.getElementById("phone"), live = [], toastT = null, cdT = null;

  function sorted() {
    var q = S.q.trim();
    var l = ORDERS.filter(function (o) { return (!S.fit || o.grade !== "C") && (!q || (o.from + o.to + o.item).indexOf(q) >= 0); });
    var key = { fare: function (o) { return -o.fare; }, near: function (o) { return o.emptyKm; }, per: function (o) { return -o.perKm; } }[S.sort];
    return l.slice().sort(function (a, b) { return key(a) - key(b); });
  }
  function gradeTag(o) { return '<span class="tag ' + o.grade.toLowerCase() + '">통과증 ' + o.grade + "</span>"; }
  function tags(o) { return gradeTag(o) + o.tags.map(function (t) { return '<span class="tag' + (t.indexOf("묶음") === 0 ? " y" : "") + '">' + t + "</span>"; }).join(""); }
  function routeTitle(o) { return esc(o.from) + " → " + esc(o.to); }
  function orderCard(o) {
    return '<button class="card" data-act="open" data-id="' + o.id + '">' +
      '<span class="row wrap">' + tags(o) + "</span>" +
      '<span class="row between"><span class="stack-1 grow"><span class="t16 b">' + routeTitle(o) + '</span><span class="t12 dim">' + o.item + " · 마대 " + o.bags + "개 · " + o.ton + "t</span></span>" +
      '<span class="stack-1 right"><span class="t20 b green num">' + won(o.fare) + '</span><span class="t12 dim">' + o.pay + "</span></span></span>" +
      '<span class="row between t12"><span class="m">' + o.when + '</span><span class="dim num">적재 ' + km1(o.km) + " · 공차 " + km1(o.emptyKm) + "</span></span></button>";
  }
  function kpis() {
    return '<div class="kpis">' + [["오늘 수입", "184,000원", 1], ["완료 운행", "2건"], ["운행 거리", "86km"]].map(function (k) { return '<div class="kpi"><span class="t12 dim m">' + k[0] + '</span><span class="t14 b num' + (k[2] ? " green" : "") + '">' + k[1] + "</span></div>"; }).join("") + "</div>";
  }
  function switchRow() {
    return '<div class="row between"><div class="stack-1"><span class="t12 dim m">운행 상태</span><span class="t20 b">' + (S.online ? "콜 받는 중" : "운행 대기 중") + '</span></div><button class="switch" role="switch" aria-checked="' + S.online + '" aria-label="콜 받기" data-act="toggle"><i></i></button></div>';
  }
  function stops(o) {
    var first = '<div class="stop"><span class="pin"></span><div class="stack-1 grow"><span class="t14 b">' + esc(o.shipper) + " · " + esc(o.from) + '</span><span class="t12 dim">' + o.window + " · " + o.cond + "</span></div></div>";
    var via = o.via ? '<div class="stop"><span class="pin"></span><div class="stack-1 grow"><span class="t14 b">' + o.via + '</span><span class="t12 dim">두 번째 상차지</span></div></div>' : "";
    return '<div class="stops">' + first + via + '<div class="stop"><span class="pin drop"></span><div class="stack-1 grow"><span class="t14 b">' + esc(o.consignee) + " · " + esc(o.to) + '</span><span class="t12 dim">' + o.dropNote + "</span></div></div></div>";
  }
  function fareBreak(o) {
    return '<div class="kpis">' + [["기본 운임", o.base], ["등급 프리미엄", o.premium], ["대기 보상", o.wait]].map(function (k) { return '<div class="stack-1"><span class="t12 dim">' + k[0] + '</span><span class="t14 b num">' + won(k[1]) + "</span></div>"; }).join("") + "</div>";
  }
  function metrics(o) { return '<span class="t12 dim num">공차 ' + km1(o.emptyKm) + " " + o.emptyMin + "분 + 적재 " + km1(o.km) + " " + o.min + "분 (예상)</span>"; }
  function steps(st) { return '<div class="steps">' + STAGES.map(function (n, i) { return '<div class="step' + (i <= st ? " on" : "") + '"><i></i>' + n + "</div>"; }).join("") + "</div>"; }
  function tabs() {
    var T = [["home", "홈", "home"], ["orders", "운반요청", "list"], ["trip", "운행중", "truck"], ["earn", "정산", "won"], ["my", "마이", "user"]];
    return '<nav class="tabs" aria-label="주요 메뉴">' + T.map(function (t) { return '<button class="tab" data-go="' + t[0] + '"' + (S.s === t[0] ? ' aria-current="page"' : "") + ">" + ic(t[2], 20) + t[1] + "</button>"; }).join("") + "</nav>";
  }
  function backFloat() { return '<div class="float-top"><button class="round" aria-label="뒤로" data-go="orders">' + ic("back") + '</button><button class="round" aria-label="내 위치에서 다시 계산" data-act="locate">' + ic("locate") + "</button></div>"; }
  function acceptFooter() {
    var over = S.cd <= 0, cl = "";
    return '<div class="footer"><button class="btn line' + cl + '" data-go="orders">건너뛰기</button><button class="btn grow' + cl + '" data-act="' + (over ? "retry" : "accept") + '">' + (over ? "시간 초과 · 다시 받기" : '수락하기 <span class="num" data-cd>0:' + ("0" + S.cd).slice(-2) + "</span>") + "</button></div>";
  }
  function tripAction(t) {
    if (t.stage === 0) return '<button class="btn lg full" data-act="stage">상차지 도착</button>';
    if (t.stage === 1) { var left = 18 - t.scanned; return '<button class="btn lg full" data-act="stage"' + (left > 0 ? " disabled" : "") + ">" + (left > 0 ? "상차 완료 · " + left + "개 더 스캔" : "상차 완료") + "</button>"; }
    if (t.stage === 2) return '<button class="btn lg full" data-act="stage">하차지 도착</button>';
    if (t.stage === 3) return '<button class="btn lg full" data-act="stage">인계서 전송 · 운행 완료</button>';
    return '<button class="btn lg full" data-go="earn">정산 내역 보기</button>';
  }
  function navLink(t, o) {
    var at = t.stage === 0 ? o.stops[0] : o.stops[o.stops.length - 1], name = t.stage === 0 ? o.shipper : o.consignee;
    return '<a class="btn line full" target="_blank" rel="noopener" href="https://map.kakao.com/link/to/' + encodeURIComponent(name) + "," + at[0] + "," + at[1] + '">' + ic("nav") + "카카오맵 길안내</a>";
  }
  function tripTitle(t, o) { return ["상차지로 이동 중", esc(o.shipper) + "에서 상차 중", esc(o.consignee) + "로 운송 중", esc(o.consignee) + "에서 하차 중", "운행 완료"][t.stage]; }
  function qrCard(t) {
    var pct = Math.round(t.scanned / 18 * 100);
    return '<div class="card"><div class="row between"><div class="stack-1"><span class="t12 dim m">마대 QR 검수</span><span class="t20 b num">' + t.scanned + ' / 18개</span></div><button class="btn" data-act="scan"' + (t.scanned >= 18 ? " disabled" : "") + ">" + ic("qr") + 'QR 스캔</button></div><div class="bar"><i style="width:' + pct + '%"></i></div><span class="t12 dim">전부 스캔해야 상차 완료 버튼이 열립니다.</span></div>';
  }
  function tripBody(t, o) {
    if (t.stage === 1) return qrCard(t);
    if (t.stage >= 3) return '<div class="card"><span class="t12 dim m">' + (t.stage === 3 ? "하차 처리" : "이번 운행") + '</span><span class="t20 b num">' + (t.stage === 3 ? "계량 후 인계서를 전송하세요" : won(o.fare) + " 정산 예정") + '</span><span class="t12 dim">폐기물 인계서는 앱이 자동으로 작성합니다.</span></div>';
    var nextName = t.stage === 0 ? o.shipper : o.consignee, info = t.stage === 0 ? km1(o.emptyKm) + " · " + o.emptyMin + "분" : km1(o.km) + " · " + o.min + "분";
    return '<div class="card"><span class="t12 dim m">다음 목적지</span><span class="t20 b">' + esc(nextName) + '</span><span class="t14 dim num">' + info + " (예상) · 화물차 조건 반영</span></div>";
  }
  function sortChips() {
    var c = [["fare", "운임순"], ["near", "가까운순"], ["per", "km당 운임"]].map(function (x) { return '<button class="chip" data-act="sort" data-k="' + x[0] + '" aria-pressed="' + (S.sort === x[0]) + '">' + x[1] + "</button>"; }).join("");
    return c;
  }

  /* 화면 */
  var B = {
    home: function () {
      return '<div class="view"><div class="appbar"><div class="bar-title"><span class="row t20 b">' + ic("pin", 16) + DEPOT.name + '</span><button class="round flat" aria-label="알림" data-act="toast" data-msg="새 알림 1건: 묶음 요청이 등록됐습니다">' + ic("bell") + '<span class="dot"></span></button></div><div class="bar-body"><span class="tag g">' + ic("truck", 16) + '5톤 윙바디 · 경기 89바 1234</span><span class="tag y">' + ic("check", 16) + '통과증 스캐너 인증</span></div></div><div class="scroll"><div class="card">' + switchRow() + "</div>" + kpis() + '<div class="row between"><span class="t16 b">받을 수 있는 요청 <span class="green num">' + sorted().length + '건</span></span><button class="btn line" data-go="orders">전체 보기</button></div>' + sorted().slice(0, 3).map(function (o) { return orderCard(o); }).join("") + "</div></div>" + tabs();
    },
    orders: function () {
      var l = sorted();
      var body = S.bmap ? '<div class="map" data-map="pins" style="margin-top:var(--s3)"></div>' : '<div class="scroll has-fab">' + l.map(function (o) { return orderCard(o); }).join("") + (l.length ? "" : '<div class="card"><span class="t14 b">조건에 맞는 요청이 없습니다</span><span class="t12 dim">검색어를 지우거나 내 차량 맞춤을 끄세요.</span></div>') + "</div>";
      return '<div class="view"><div class="appbar"><div class="bar-title"><span class="t20 b">운반 요청 <span class="num">' + l.length + '</span>건</span></div><div class="bar-body"><label class="search grow">' + ic("search", 16) + '<input id="q" aria-label="출발지, 도착지, 품목 검색" placeholder="출발지, 도착지, 품목 검색" value="' + esc(S.q).replace(/"/g, "&quot;") + '"></label></div></div><div class="subbar"><div class="chips"><button class="chip" data-act="fit" aria-pressed="' + S.fit + '">내 차량 맞춤</button>' + sortChips() + "</div></div>" + body + '<button class="btn fab" data-act="bmap">' + ic(S.bmap ? "list" : "map") + (S.bmap ? "목록 보기" : "지도 보기") + "</button></div>" + tabs();
    },
    detail: function () {
      var o = byId(S.id);
      return '<div class="view"><div class="map fixed" data-map="selected" style="height:280px"></div>' + backFloat() + '<div class="scroll"><div class="card"><div class="row between"><span class="stack-1"><span class="t12 dim m">총 운임 · 수수료 0원</span><span class="t28 b green num">' + won(o.fare) + '</span></span><span class="stack-1 right"><span class="t12 dim">km당 운임</span><span class="t14 b num">' + won(o.perKm) + "</span></span></div>" + metrics(o) + '<div class="row wrap">' + tags(o) + '<span class="tag">' + o.pay + '</span></div></div><div class="card">' + stops(o) + '</div><div class="card">' + fareBreak(o) + '</div><div class="card"><div class="stack" style="gap:var(--s3)"><div class="list-row"><span class="t14">품목</span><span class="t14 b">' + o.item + '</span></div><div class="list-row"><span class="t14">마대 · 중량</span><span class="t14 b num">' + o.bags + "개 · " + o.ton + 't</span></div><div class="list-row"><span class="t14">화주 평점</span><span class="t14 b num">' + o.rating + " / 5.0</span></div></div></div></div></div>" + acceptFooter();
    },
    trip: function () {
      var t = S.trip, o = byId(t.id);
      var items = t.stage === 1 ? '<div class="card"><div class="stack" style="gap:var(--s3)"><div class="list-row"><span class="stack-1"><span class="t14 b num">KM-0042-000883</span><span class="t12 dim">PP · 198kg · 순도 98.1%</span></span>' + ic("check") + '</div><div class="list-row"><span class="stack-1"><span class="t14 b num">KM-0042-000879</span><span class="t12 warn">사진에서 PE 혼입 의심</span></span><button class="btn line" data-act="toast" data-msg="적재 사진을 엽니다 (시연)">사진 보기</button></div></div></div>' : "";
      return '<div class="view"><div class="appbar"><div class="bar-title"><span class="t20 b">' + tripTitle(t, o) + '</span><span class="t12 dim num">PASS-2026-000123</span></div><div class="bar-body">' + steps(t.stage) + '</div></div><div class="scroll">' + tripBody(t, o) + items + '<div class="card flush"><div class="map fixed" data-map="trip" style="height:176px"></div></div>' + navLink(t, o) + '</div><div class="footer">' + tripAction(t) + "</div></div>" + tabs();
    }
  };
  function earn() {
    var head = '<div class="appbar"><div class="bar-title"><span class="t20 b">정산</span></div><div class="bar-body between"><span class="t28 b num">' + won(WEEK_TOTAL) + '</span><span class="stack-1 right"><span class="t12 dim">10.28 ~ 11.03 수입</span><span class="t12 m">운행 7건 · 묶음 3건</span></span></div></div>';
    var settle = '<div class="card"><div class="row between"><div class="stack-1"><span class="t12 dim m">다음 정산 · 11.06 (금) 입금</span><span class="t20 b num">' + won(PENDING) + '</span><span class="t12 dim">세금계산서 자동 발행 · 수수료 0원</span></div><button class="btn line" data-act="toast" data-msg="세금계산서 내역을 엽니다 (시연)">내역</button></div></div>';
    var promo = '<div class="card accent-card"><span class="t12 dim m">주유 쿠폰</span><span class="t14 b">이번 주 묶음 운행 3건 달성 · 15,000원 지급</span></div>';
    var rows = LEDGER.map(function (l) { return '<div class="list-row"><span class="stack-1 grow"><span class="t14 b">' + l.n + (l.bundle ? ' <span class="tag y">묶음</span>' : "") + '</span><span class="t12 dim">' + l.d + '</span></span><span class="stack-1 right"><span class="t14 b num">' + won(l.v) + '</span><span class="t12 ' + (l.s === "정산 예정" ? "warn" : "dim") + '">' + l.s + "</span></span></div>"; }).join("");
    return '<div class="view">' + head + '<div class="scroll">' + settle + promo + '<div class="card"><span class="t16 b">운행 내역</span><div class="stack" style="gap:var(--s3)">' + rows + "</div></div></div></div>" + tabs();
  }
  function my() {
    var g = window.ROAD_GRAPH.meta;
    return '<div class="view"><div class="appbar"><div class="bar-title"><span class="t20 b">마이</span></div><div class="bar-body"><span class="t14 m">경기 89바 1234 · 5톤 윙바디</span></div></div><div class="scroll"><div class="card"><span class="t16 b">경로 계산에 쓰는 차량 조건</span><div class="stack" style="gap:var(--s3)"><div class="list-row"><span class="t14">전고</span><span class="t14 b num">' + g.vehicle.heightM + 'm</span></div><div class="list-row"><span class="t14">총중량</span><span class="t14 b num">' + g.vehicle.grossT + 't</span></div><div class="list-row"><span class="t14">통행 제한으로 뺀 도로</span><span class="t14 b num">' + g.excludedWays + '구간</span></div></div><span class="t12 dim">높이·중량 제한이 차량 조건에 걸리는 도로는 경로에서 뺍니다.</span></div><div class="card"><span class="t16 b">내 인증</span><div class="row wrap"><span class="tag y">' + ic("check", 16) + '통과증 스캐너 인증</span><span class="tag">인계서 자동 작성</span></div></div><div class="card"><div class="list-row"><span class="stack-1"><span class="t12 dim m">차고지</span><span class="t14 b">' + DEPOT.name + '</span></span><span class="t12 dim num">' + DEPOT.at.join(", ") + "</span></div></div></div></div>" + tabs();
  }

  function render() {
    live.forEach(function (m) { m.remove(); }); live = [];
        var html = S.s === "earn" ? earn() : S.s === "my" ? my() : B[S.s]();
    phone.innerHTML = html + (S.toast ? '<div class="toast" role="status">' + esc(S.toast) + "</div>" : "");
    Array.prototype.forEach.call(phone.querySelectorAll("[data-map]"), mountMap);
        clearInterval(cdT);
    if (S.s === "detail") cdT = setInterval(tick, 1000);
    try { history.replaceState(null, "", "#" + S.s); } catch (e) { /* 샌드박스에서는 무시 */ }
  }
  function tick() {
    if (S.cd <= 0) { clearInterval(cdT); return; }
    S.cd--;
    if (S.cd === 0) return render();
    var a = phone.querySelector("[data-cd]"); if (a) a.textContent = "0:" + ("0" + S.cd).slice(-2);
  }
  function addTiles(m) {
    return new DataTiles("", { minZoom: LIVE ? 6 : 10, minNativeZoom: LIVE ? undefined : 10, maxNativeZoom: LIVE ? 19 : 13, maxZoom: LIVE ? 19 : 15, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> 기여자' }).addTo(m);
  }
  function baseMap(el) {
    var m = L.map(el, { zoomControl: false, minZoom: LIVE ? 6 : 10, maxZoom: LIVE ? 19 : 15, maxBounds: LIVE ? null : TILE_BOUNDS, maxBoundsViscosity: 1, zoomSnap: 0.25, attributionControl: true });
    m.attributionControl.setPrefix(false);
    addTiles(m);
    return m;
  }
  function divIcon(cls, html, w, h) { return L.divIcon({ className: "", html: '<div class="mk ' + cls + '">' + (html || "") + "</div>", iconSize: [w, h], iconAnchor: [w / 2, h / 2] }); }
  function dot(m, at, cls) { L.marker(at, { icon: divIcon(cls, "", 20, 20), keyboard: false, interactive: false }).addTo(m); }
  function truck(m, at) { L.marker(at, { icon: divIcon("mk-truck", ic("truck", 16), 32, 32), keyboard: false, interactive: false, zIndexOffset: 500 }).addTo(m); }
  function label(m, at, text, dir) {
    var i = L.divIcon({ className: "", html: '<div class="mk mk-label" style="transform:translate(-50%,' + (dir === "up" ? "-170%" : "60%") + ')">' + text + "</div>", iconSize: [0, 0] });
    L.marker(at, { icon: i, keyboard: false, interactive: false }).addTo(m);
  }
  function lineOn(m, coords, color, dash) {
    if (!dash) L.polyline(coords, { color: "#FFFFFF", weight: 8, opacity: .9, lineJoin: "round", interactive: false }).addTo(m);
    L.polyline(coords, { color: color, weight: dash ? 4 : 5, dashArray: dash || null, lineJoin: "round", interactive: false }).addTo(m);
  }
  function drawOrder(m, o) {
    lineOn(m, o.empty.coords, "#5C6963", "2 8");
    lineOn(m, o.line, "#1F5A3F");
    truck(m, S.me || DEPOT.at);
    o.stops.slice(0, -1).forEach(function (s) { dot(m, s, "mk-pick"); });
    dot(m, o.stops[o.stops.length - 1], "mk-drop");
    label(m, o.stops[0], "상차", "up");
    label(m, o.stops[o.stops.length - 1], "하차", "down");
  }
  function mountMap(el) {
    var kind = el.getAttribute("data-map"), m = baseMap(el); live.push(m);
    var inFlow = !el.classList.contains("fixed");
    var top = kind === "trip" ? 24 : (inFlow ? 40 : 40);
    var pad = { paddingTopLeft: [inFlow ? 40 : 72, top], paddingBottomRight: [40, inFlow ? 72 : 48], maxZoom: LIVE ? 15 : 13 };
    m.invalidateSize();
    if (kind === "pins") {
      var pts = [S.me || DEPOT.at];
      truck(m, S.me || DEPOT.at);
      sorted().forEach(function (o) {
        pts.push(o.stops[0]);
        var i = L.divIcon({ className: "", html: '<button class="mk mk-fare" style="transform:translate(-50%,-50%)" aria-label="' + routeTitle(o) + " " + won(o.fare) + '">' + (o.fare / 10000).toFixed(1) + "만</button>", iconSize: [0, 0] });
        L.marker(o.stops[0], { icon: i, keyboard: false }).on("click", function () { openDetail(o.id); }).addTo(m);
      });
      m.fitBounds(pts, pad);
    } else if (kind === "selected") {
      var o = byId(S.id); drawOrder(m, o);
      m.fitBounds(o.empty.coords.concat(o.line), pad);
    } else {
      var t = S.trip, od = byId(t.id), col = "#1F5A3F", at, coords;
      if (t.stage === 0) { coords = od.empty.coords; at = S.me || DEPOT.at; }
      else { coords = od.line; at = t.stage === 1 ? od.stops[0] : t.stage === 2 ? coords[Math.floor(coords.length * .4)] : od.stops[od.stops.length - 1]; }
      lineOn(m, coords, col);
      if (t.stage === 0) dot(m, od.stops[0], "mk-pick");
      else { od.stops.slice(0, -1).forEach(function (s) { dot(m, s, "mk-pick"); }); dot(m, od.stops[od.stops.length - 1], "mk-drop"); }
      truck(m, at);
      m.fitBounds(coords, pad);
    }
  }
  function setOrigin(at) {
    S.me = at;
    ORDERS.forEach(function (o) { o.empty = router.route(at, o.stops[0]); o.emptyKm = o.empty.meters / 1000; o.emptyMin = Math.round(o.empty.seconds / 60); o.perKm = Math.round(o.fare / (o.km + o.emptyKm)); });
  }
  function locate() {
    if (!navigator.geolocation) return say("이 브라우저에서는 위치를 쓸 수 없습니다.");
    navigator.geolocation.getCurrentPosition(function (p) {
      var at = [p.coords.latitude, p.coords.longitude];
      if (!inGraph(at)) return say("지금 위치는 내장 경로 범위(안산·시흥·화성) 밖입니다.");
      setOrigin(at); say("내 위치 기준으로 공차 거리를 다시 계산했습니다.");
    }, function () { say("위치를 가져오지 못했습니다. 브라우저에서 위치 권한을 허용해 주세요."); }, { enableHighAccuracy: true, timeout: 10000 });
  }
  function openDetail(id) { S.id = id; S.cd = 45; S.s = "detail"; render(); }
  function say(msg) { S.toast = msg; render(); clearTimeout(toastT); toastT = setTimeout(function () { S.toast = ""; render(); }, 2400); }

  phone.addEventListener("click", function (e) {
    var b = e.target.closest("[data-go],[data-act]"); if (!b) return;
    var go = b.getAttribute("data-go"), act = b.getAttribute("data-act");
    if (go) { S.s = go; return render(); }
    var id = +b.getAttribute("data-id");
    if (act === "toggle") { S.online = !S.online; render(); }
    else if (act === "open") openDetail(id);
    else if (act === "sort") { S.sort = b.getAttribute("data-k"); render(); }
    else if (act === "fit") { S.fit = !S.fit; render(); }
    else if (act === "bmap") { S.bmap = !S.bmap; render(); }
    else if (act === "accept") { S.trip = { id: S.id, stage: 0, scanned: 0 }; S.s = "trip"; render(); }
    else if (act === "retry") { S.cd = 45; render(); }
    else if (act === "scan") { S.trip.scanned = Math.min(18, S.trip.scanned + 1); render(); }
    else if (act === "stage") { S.trip.stage = Math.min(4, S.trip.stage + 1); render(); }
    else if (act === "locate") locate();
    else if (act === "toast") say(b.getAttribute("data-msg"));
  });
  phone.addEventListener("input", function (e) {
    if (e.target.id !== "q") return;
    S.q = e.target.value; var pos = e.target.selectionStart; render();
    var q = document.getElementById("q"); if (q) { q.focus(); q.setSelectionRange(pos, pos); }
  });

  /* 좌표 실험 */
  var lab = baseMap(document.getElementById("labmap")), labLayer = L.layerGroup().addTo(lab), nextEnd = "from";
  lab.fitBounds(BOUNDS);
  var f = { fa: document.getElementById("fromLat"), fo: document.getElementById("fromLon"), ta: document.getElementById("toLat"), to: document.getElementById("toLon") };
  var labToken = 0;
  function labMsg(t) { document.getElementById("labstat").innerHTML = "<tr><th>" + esc(t) + "</th></tr>"; }
  function labShow(r, a, b, source) {
    labLayer.clearLayers();
    L.polyline(r.coords, { color: "#FFF", weight: 7 }).addTo(labLayer); L.polyline(r.coords, { color: "#1F5A3F", weight: 4 }).addTo(labLayer);
    L.marker(a, { icon: divIcon("mk-pick", "", 20, 20), interactive: false }).addTo(labLayer); L.marker(b, { icon: divIcon("mk-drop", "", 20, 20), interactive: false }).addTo(labLayer);
    lab.fitBounds(r.coords, { padding: [24, 24] });
    document.getElementById("labstat").innerHTML = [["거리", km1(r.meters / 1000)], ["예상 시간 (정체 미반영)", Math.round(r.seconds / 60) + "분"], ["탐색한 교차점", r.settled.toLocaleString("ko-KR") + " / " + r.totalNodes.toLocaleString("ko-KR")], ["계산 시간", r.computeMs.toFixed(1) + "ms"], ["도로까지 보정 거리", r.snapFrom + "m / " + r.snapTo + "m"], ["도로 데이터", source]].map(function (x) { return "<tr><th>" + x[0] + "</th><td>" + x[1] + "</td></tr>"; }).join("");
    window.__lastRoute = { km: r.meters / 1000, min: r.seconds / 60, source: source };
  }
  function labRun() {
    var a = [parseFloat(f.fa.value), parseFloat(f.fo.value)], b = [parseFloat(f.ta.value), parseFloat(f.to.value)], token = ++labToken;
    if (a.concat(b).some(isNaN) || Math.abs(a[0]) > 90 || Math.abs(b[0]) > 90 || Math.abs(a[1]) > 180 || Math.abs(b[1]) > 180) return labMsg("좌표를 숫자로 입력해 주세요. 예: 위도 37.3055, 경도 126.79");
    if (inGraph(a) && inGraph(b)) {
      var r = router.route(a, b);
      if (!r) return labMsg("두 지점을 잇는 도로를 찾지 못했습니다.");
      return labShow(r, a, b, "내장");
    }
    if (!LIVE) return labMsg("인터넷 연결 없이는 안산·시흥·화성 범위 안에서만 계산합니다.");
    var direct = Dijkstra.haversine(a, b) / 1000;
    if (direct > 100) return labMsg("직선거리 100km 이내만 실시간으로 계산합니다. 지금은 " + Math.round(direct) + "km입니다.");
    labMsg("실제 도로 데이터를 받는 중입니다.");
    var post = function (host) { var ctl = new AbortController(), tm = setTimeout(function () { ctl.abort(); }, 40000); return fetch(host + "/api/interpreter", { signal: ctl.signal, method: "POST", body: "data=" + encodeURIComponent(RoadNet.query(a, b, direct)), headers: { "Content-Type": "application/x-www-form-urlencoded" } }).then(function (res) { if (!res.ok) throw new Error("HTTP " + res.status); return res.json(); }).finally(function () { clearTimeout(tm); }); };
    post("https://overpass-api.de").catch(function () { return post("https://overpass.kumi.systems"); })
      .then(function (osm) {
        if (token !== labToken) return;
        var g = RoadNet.build(osm, window.ROAD_GRAPH.meta.vehicle, [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]);
        var r2 = g && Dijkstra.createRouter(g).route(a, b);
        if (!r2) return labMsg("두 지점을 잇는 도로를 찾지 못했습니다.");
        if (r2.snapFrom > 1000 || r2.snapTo > 1000) return labMsg("좌표 근처 1km 안에 화물차가 다닐 도로가 없습니다. 좌표를 도로 가까이 옮겨 주세요.");
        labShow(r2, a, b, "실시간");
      })
      .catch(function () { if (token === labToken) labMsg("도로 데이터 서버가 응답하지 않습니다. 잠시 뒤 다시 눌러 주세요."); });
  }
  function searchPlace(end) {
    var q = document.getElementById("place").value.trim(); if (!q) return labMsg("찾을 주소나 장소를 입력해 주세요.");
    if (!LIVE) return labMsg("주소 검색은 인터넷 연결이 필요합니다. 좌표를 직접 넣어 주세요.");
    labMsg("주소를 찾는 중입니다.");
    fetch("https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=kr&q=" + encodeURIComponent(q))
      .then(function (res) { if (!res.ok) throw new Error("HTTP " + res.status); return res.json(); })
      .then(function (l) {
        if (!l.length) return labMsg("검색 결과가 없습니다. 시·군·구까지 넣어 다시 찾아보세요.");
        var la = (+l[0].lat).toFixed(5), lo = (+l[0].lon).toFixed(5);
        if (end === "from") { f.fa.value = la; f.fo.value = lo; } else { f.ta.value = la; f.to.value = lo; }
        labRun();
      })
      .catch(function () { labMsg("주소 검색 서버가 응답하지 않습니다. 좌표를 직접 넣어 주세요."); });
  }
  document.getElementById("placeFrom").addEventListener("click", function () { searchPlace("from"); });
  document.getElementById("placeTo").addEventListener("click", function () { searchPlace("to"); });
  lab.on("click", function (e) { var la = e.latlng.lat.toFixed(5), lo = e.latlng.lng.toFixed(5); if (nextEnd === "from") { f.fa.value = la; f.fo.value = lo; nextEnd = "to"; } else { f.ta.value = la; f.to.value = lo; nextEnd = "from"; labRun(); } });
  document.getElementById("labform").addEventListener("submit", function (e) { e.preventDefault(); labRun(); });
  f.fa.value = 37.3055; f.fo.value = 126.79; f.ta.value = 37.1235; f.to.value = 126.9105; labRun();
  var meta = window.ROAD_GRAPH.meta;
  function labNote() { document.getElementById("labmeta").textContent = (LIVE ? "지도: 실시간 OpenStreetMap. 전국을 이동·확대할 수 있고 범위 밖 좌표는 실제 도로 데이터를 받아 계산합니다." : "지도: 내장 OpenStreetMap (" + meta.extractedAt.slice(0, 10) + " 기준). 인터넷을 쓸 수 없어 안산·시흥·화성 일대만 표시합니다.") + " 일방통행과 차량 제한을 반영했고, 회전 제한과 실시간 교통은 반영하지 않았습니다."; }
  labNote();

  var h = (location.hash || "").match(/^#(home|orders|trip|earn|my)$/);
  if (h) S.s = h[1];
  window.__app = { S: S, render: render, orders: ORDERS, openDetail: openDetail, live: function () { return LIVE; } };
  render();
  var probe = new Image();
  probe.onload = function () {
    LIVE = true;
    lab.setMaxBounds(null); lab.setMinZoom(6); lab.setMaxZoom(19);
    lab.eachLayer(function (l) { if (l instanceof L.TileLayer) lab.removeLayer(l); });
    addTiles(lab); labNote(); render();
  };
  probe.src = "https://tile.openstreetmap.org/14/13963/6362.png";
})();
