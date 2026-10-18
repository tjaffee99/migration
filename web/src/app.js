/* Atlas of Arrivals — client app. Reads window.__DATA__ (built by scripts/build/build_data.py)
   and window.__GEO__ (built by scripts/build/build_site.py). No network access at runtime. */
(function () {
  "use strict";
  const D = window.__DATA__;
  const G = window.__GEO__;
  const Y0 = D.start, Y1 = D.end, NY = Y1 - Y0 + 1;
  const SY = D.stock.years;
  const STOCK_FIRST = SY[0];

  // ---------- helpers ----------
  const $ = (id) => document.getElementById(id);
  const fmtInt = d3.format(",");
  const compactFmt = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
  const compact = (n) => (n == null ? "—" : Math.abs(n) < 1000 ? String(Math.round(n)) : compactFmt.format(n));
  const pct = (x) => (x == null ? "—" : x < 0.005 ? "<1%" : x < 0.1 ? (x * 100).toFixed(1) + "%" : Math.round(x * 100) + "%");
  const roundEst = (n) => (n < 100 ? Math.round(n) : n < 1000 ? Math.round(n / 10) * 10 : n < 100000 ? Math.round(n / 100) * 100 : Math.round(n / 1000) * 1000);
  const fmtCount = (v, approx) => (approx ? "≈" + fmtInt(roundEst(v)) : fmtInt(Math.round(v)));
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const norm = (x, y) => { const l = Math.hypot(x, y) || 1; return [x / l, y / l]; };

  // ---------- lookups ----------
  const groups = D.groups;
  const groupById = Object.fromEntries(groups.map((g) => [g.id, g]));
  const origins = D.origins;
  const originById = Object.fromEntries(origins.map((o) => [o.id, o]));
  let color = {};
  const readColors = () => { color = Object.fromEntries(groups.map((g) => [g.id, css("--s" + g.slot)])); };
  readColors();
  const basisInfo = (code) => D.basisInfo[code] || { label: "", cls: "" };

  const expand = ([s, vals]) => {
    const a = new Float64Array(NY);
    for (let i = 0; i < vals.length && s + i < NY; i++) a[s + i] = vals[i] || 0;
    return a;
  };
  const legalBy = {};
  for (const [id, sp] of Object.entries(D.flow.o)) legalBy[id] = expand(sp);
  const unBy = {};
  for (const [id, sp] of Object.entries(D.flow.u || {})) unBy[id] = expand(sp);
  const flowIds = [...new Set([...Object.keys(legalBy), ...Object.keys(unBy)])].filter((id) => originById[id]);
  const legalAt = (id, i) => (legalBy[id] ? legalBy[id][i] : 0);
  const unAt = (id, i) => (unBy[id] ? unBy[id][i] : 0);
  const HAS_UN = Object.keys(unBy).length > 0;

  const flowGroups = []; // per year: {year, g: legal, "g~u": illegal (estimated)}
  for (let i = 0; i < NY; i++) {
    const row = { year: Y0 + i };
    for (const g of groups) { row[g.id] = 0; row[g.id + "~u"] = 0; }
    for (const id of flowIds) {
      const g = originById[id].group;
      row[g] += legalAt(id, i);
      row[g + "~u"] += unAt(id, i);
    }
    flowGroups.push(row);
  }
  function interp(vals, y) {
    if (!vals || y < SY[0] || y > SY[SY.length - 1]) return null;
    const i = d3.bisectRight(SY, y) - 1;
    if (SY[i] === y) return vals[i] == null ? null : { v: vals[i], exact: true, a: y, b: y };
    const a = vals[i], b = vals[i + 1];
    if (a == null || b == null) return null;
    const t = (y - SY[i]) / (SY[i + 1] - SY[i]);
    return { v: a + (b - a) * t, exact: false, a: SY[i], b: SY[i + 1] };
  }
  const modelBy = {};
  for (const [id, sp] of Object.entries(D.fbModel.o)) modelBy[id] = expand(sp);
  const MODEL_UNTIL = D.fbModel.until;

  // immigrants living in the US at year y: modelled before the first birthplace census, then census/survey
  function stockAt(y) {
    const i = y - Y0;
    const m = new Map();
    let total = 0, kind, a = y, b = y;
    if (y <= MODEL_UNTIL) {
      for (const [id, arr] of Object.entries(modelBy)) if (arr[i] > 0.5) { m.set(id, arr[i]); total += arr[i]; }
      kind = "model";
    } else {
      const t = interp(D.stock.nat.total, y);
      if (!t) return null;
      total = t.v;
      a = t.a; b = t.b;
      for (const [id, arr] of Object.entries(D.stock.nat.o)) {
        const r = interp(arr, y);
        if (r && r.v > 0.5 && originById[id]) m.set(id, r.v);
      }
      kind = t.exact ? D.stock.kind[SY.indexOf(y)] : "interp";
    }
    let pop = D.pop[i];
    if (pop == null) { const p = interp(D.stock.nat.pop, y); pop = p ? p.v : null; }
    return { m, total, pop, kind, a, b };
  }
  const stockGroups = [];
  for (let y = Y0; y <= Y1; y++) {
    const row = { year: y };
    for (const g of groups) row[g.id] = 0;
    if (y <= MODEL_UNTIL) {
      for (const [id, arr] of Object.entries(modelBy)) row[originById[id].group] += arr[y - Y0];
    } else {
      for (const g of groups) { const r = interp(D.stock.nat.g[g.id], y); row[g.id] = r ? r.v : 0; }
    }
    stockGroups.push(row);
  }

  function flowsAt(y) {
    const i = y - Y0;
    const list = [];
    let un = 0;
    for (const id of flowIds) {
      const l = legalAt(id, i), u = unAt(id, i);
      if (l + u > 0) list.push({ id, v: l + u, legal: l, un: u });
      un += u;
    }
    list.sort((p, q) => q.v - p.v);
    const legal = D.flow.total[i];
    return { list, legal, un, total: legal == null && !un ? null : (legal || 0) + un, basis: D.flow.basis[i], unBasis: D.flow.uBasis ? D.flow.uBasis[i] : null };
  }

  // ---------- state ----------
  const hashYear = parseInt((location.hash || "").replace("#", ""), 10);
  const S = {
    year: hashYear >= Y0 && hashYear <= Y1 ? hashYear : D.defaultYear || 1910,
    origin: null,
    series: "flow",
    chartScale: "count",
    widthScale: "all",
    showAll: false,
    query: "",
    playing: false,
    timer: null,
  };

  // ---------- tooltip ----------
  const tip = $("tip");
  function showTip(evt, build) {
    tip.replaceChildren();
    build(tip);
    tip.hidden = false;
    moveTip(evt);
  }
  function moveTip(evt) {
    const r = tip.getBoundingClientRect();
    let x = evt.clientX + 14, y = evt.clientY + 14;
    if (x + r.width > innerWidth - 8) x = evt.clientX - r.width - 14;
    if (y + r.height > innerHeight - 8) y = evt.clientY - r.height - 14;
    tip.style.left = clamp(x, 8, innerWidth - r.width - 8) + "px";
    tip.style.top = clamp(y, 8, innerHeight - r.height - 8) + "px";
  }
  const hideTip = () => { tip.hidden = true; };
  function tipRow(parent, c, label, value) {
    const row = el("div", "row");
    const i = el("i");
    i.style.background = c || "transparent";
    row.append(i, el("span", null, label), el("b", null, value));
    parent.append(row);
  }

  // ---------- world map ----------
  // Centred on 90°W so Europe and Africa sit east of the US and East Asia west, across the Pacific.
  const proj0 = () => d3.geoEqualEarth().rotate([90, 0]);
  const modern = topojson.feature(G.world, G.world.objects.countries).features.filter((f) => f.properties.iso3 !== "ATA");
  const landShape = { type: "FeatureCollection", features: modern };
  const hist = G.hist ? topojson.feature(G.hist, G.hist.objects.polities).features : null;
  const polities = hist || modern.map((f) => Object.assign(f, { properties: Object.assign({}, f.properties, { name: f.properties.name }) }));
  const politiesAt = (y) => (hist ? (G.histYears[y] || []) : polities.map((_, k) => k));
  const jurs = topojson.feature(G.us, G.us.objects.jurisdictions).features;

  // origins whose arrow starts inside each polity (computed once per polity)
  const inside = new Map();
  const originsIn = (k) => {
    if (!inside.has(k)) {
      const f = polities[k];
      inside.set(k, origins.filter((o) => o.at && d3.geoContains(f, o.at)).map((o) => o.id));
    }
    return inside.get(k);
  };

  // merge trees: one per world region; Asia is split by the ocean its arrivals cross
  const treeOf = (o) => {
    if (!o.at) return null;
    if (o.forced || o.group === "afr") return "afr";
    if (o.to === "north") return "can";
    if (["bri", "nwe", "see"].includes(o.group) || (o.group === "oth" && o.to === "east")) return "eur";
    if (o.group === "asi") return o.to === "west" ? "asi_w" : "asi_e";
    if (o.group === "oth") return "oce";
    return o.group;
  };
  const TREE_NAME = { eur: "Europe", afr: "Africa", asi_w: "East & Southeast Asia", asi_e: "South & West Asia", oce: "Oceania & Pacific", lat: "Caribbean & Latin America", mex: "Mexico", can: "Canada" };
  const treeName = (k) => TREE_NAME[k] || k;
  const allTime = {};
  for (const id of flowIds) {
    let s = 0;
    for (let i = 0; i < NY; i++) s += legalAt(id, i) + unAt(id, i);
    allTime[id] = s;
  }
  // one width scale for every year: the widest trunk carries the largest regional flow on record
  let MAXT = 0;
  for (let i = 0; i < NY; i++) {
    const t = {};
    for (const id of flowIds) { const k = treeOf(originById[id]); if (k) t[k] = (t[k] || 0) + legalAt(id, i) + unAt(id, i); }
    for (const v of Object.values(t)) if (v > MAXT) MAXT = v;
  }
  const POP_MAX = d3.max(D.pop) || 3.4e8;

  const mapBox = $("map");
  const svg = d3.select(mapBox).append("svg");
  const gZoom = svg.append("g");
  const gLand = gZoom.append("g");
  const gPol = gZoom.append("g");
  const gUS = gZoom.append("g");
  const gArrows = gZoom.append("g");
  const gFlow = gZoom.append("g");
  const gDonut = gZoom.append("g").attr("class", "donut");
  const gLabels = gZoom.append("g");
  const gHit = gZoom.append("g");
  let proj, path, W = 1200, H = 600, wMax = 40, rMax = 50, treeCen = {};
  // zoom: drag to pan; pinch, Ctrl/⌘+scroll, double-click or the buttons to zoom
  let zt = d3.zoomIdentity;
  let last = null; // the latest drawn year's map state, for redrawing labels while zooming
  let zRaf = 0;
  const zoom = d3.zoom().scaleExtent([1, 10]).clickDistance(4)
    // on touch screens one finger scrolls the page until the map is zoomed in; two fingers zoom
    .filter((e) => (e.type === "wheel" ? e.ctrlKey || e.metaKey : e.type === "touchstart" ? e.touches.length > 1 || zt.k > 1 : !e.button))
    .on("zoom", (e) => {
      zt = e.transform;
      gZoom.attr("transform", zt);
      svg.style("touch-action", zt.k > 1 ? "none" : "pan-y");
      if (!zRaf) zRaf = requestAnimationFrame(() => { zRaf = 0; if (last) { drawDonutLabels(); drawLabels(); } });
    });
  svg.call(zoom);
  const zoomBy = (f) => svg.transition().duration(250).call(zoom.scaleBy, f);
  const zoomReset = () => svg.transition().duration(300).call(zoom.transform, d3.zoomIdentity);
  function zoomToUS() {
    if (!last) return;
    const k = clamp((Math.min(W, H) * 0.32) / (last.r || 20), 2, 10);
    const [cx, cy] = last.C;
    svg.transition().duration(450).call(zoom.transform, d3.zoomIdentity.translate(W / 2 - cx * k, H / 2 - cy * k).scale(k));
  }
  {
    const ctl = el("div", "zoom-ctl");
    for (const [label, aria, fn] of [["+", "Zoom in", () => zoomBy(1.6)], ["−", "Zoom out", () => zoomBy(1 / 1.6)], ["US", "Zoom to the United States and its population circle", zoomToUS], ["⟲", "Reset zoom", zoomReset]]) {
      const b = el("button", null, label);
      b.type = "button";
      b.setAttribute("aria-label", aria);
      b.title = aria;
      b.addEventListener("click", fn);
      ctl.append(b);
    }
    mapBox.append(ctl);
  }
  const motion = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  const polPath = new Map(), usPath = new Map(), usCen = new Map();

  function layoutMap() {
    W = Math.max(320, mapBox.clientWidth || 1200);
    proj = proj0().fitWidth(W, landShape);
    path = d3.geoPath(proj);
    const b = path.bounds(landShape);
    const pad = 8;
    proj.translate([proj.translate()[0], proj.translate()[1] - b[0][1] + pad]);
    H = Math.ceil(b[1][1] - b[0][1] + pad * 2);
    svg.attr("viewBox", `0 0 ${W} ${H}`);
    zoom.extent([[0, 0], [W, H]]).translateExtent([[0, 0], [W, H]]);
    zt = d3.zoomIdentity;
    svg.call(zoom.transform, zt);
    wMax = clamp(W / 28, 12, 44);
    rMax = clamp(W / 22, 14, 58);
    polPath.clear(); usPath.clear(); usCen.clear();
    gLand.selectAll("path").data([landShape]).join("path").attr("class", "land-base").attr("d", path);
    // where each region's branches join: flow-weighted centre of its origins
    treeCen = {};
    const acc = {};
    for (const id of flowIds) {
      const o = originById[id], k = treeOf(o);
      if (!k) continue;
      const p = proj(o.at);
      if (!p) continue;
      const w = Math.max(allTime[id], 1);
      acc[k] = acc[k] || [0, 0, 0];
      acc[k][0] += p[0] * w; acc[k][1] += p[1] * w; acc[k][2] += w;
    }
    for (const [k, [x, y, w]] of Object.entries(acc)) treeCen[k] = [x / w, y / w];
  }
  const polD = (k) => { if (!polPath.has(k)) polPath.set(k, path(polities[k]) || ""); return polPath.get(k); };
  const usD = (k) => { if (!usPath.has(k)) usPath.set(k, path(jurs[k]) || ""); return usPath.get(k); };

  // the US circle sits at the area-weighted centre of the country (or colonies) that year
  function usCentre(y) {
    if (usCen.has(y)) return usCen.get(y);
    const ids = (G.usYears[y] || []).filter((k) => jurs[k].properties.type !== "other" && !["02", "15"].includes(jurs[k].properties.fips));
    let x = 0, yy = 0, a = 0;
    for (const k of ids) {
      const ar = path.area(jurs[k]);
      const c = path.centroid(jurs[k]);
      if (!ar || !isFinite(c[0])) continue;
      x += c[0] * ar; yy += c[1] * ar; a += ar;
    }
    const c = a ? [x / a, yy / a] : proj([-77, 38]);
    usCen.set(y, c);
    return c;
  }

  function cubic(p0, p1, p2, p3) {
    return `M${p0[0]},${p0[1]}C${p1[0]},${p1[1]} ${p2[0]},${p2[1]} ${p3[0]},${p3[1]}`;
  }
  const up = (v) => (v[1] > 0 ? [-v[0], -v[1]] : v); // normal pointing north

  // Each region's arrows run side by side into one bundle at a merge point, then on to the US circle
  // as one arrow; every origin keeps its own lane (its width) all the way in.
  function quadAt(p0, q, p1, t) {
    const a = (1 - t) * (1 - t), b = 2 * (1 - t) * t, c = t * t;
    return [a * p0[0] + b * q[0] + c * p1[0], a * p0[1] + b * q[1] + c * p1[1]];
  }
  function buildTrees(y, C, r) {
    const i = y - Y0;
    const trees = new Map();
    for (const id of flowIds) {
      const o = originById[id], k = treeOf(o);
      const v = legalAt(id, i) + unAt(id, i);
      if (!k || !(v > 0)) continue;
      const p = proj(o.at);
      if (!p) continue;
      if (!trees.has(k)) trees.set(k, { key: k, branches: [], total: 0, un: 0, forced: 0 });
      const t = trees.get(k);
      t.branches.push({ id, v, un: unAt(id, i), p0: p });
      t.total += v;
      t.un += unAt(id, i);
      if (o.forced) t.forced += v;
    }
    const list = [...trees.values()];
    const top = S.widthScale === "year" ? d3.max(list, (t) => t.total) || 1 : MAXT;
    const kpx = wMax / top;
    // merge points and widths
    for (const t of list) {
      const cen = treeCen[t.key] || t.branches[0].p0;
      t.M = [cen[0] + (C[0] - cen[0]) * 0.45, cen[1] + (C[1] - cen[1]) * 0.45];
      const raw = t.total * kpx;
      t.W = Math.max(1.4, raw);
      t.s = raw ? t.W / raw : 1;
      t.theta = Math.atan2(t.M[1] - C[1], t.M[0] - C[0]);
      t.half = Math.min(Math.PI / 2.2, (t.W / 2 + 2) / (r + 3));
    }
    // spread the arrival points around the circle so arrows from nearby regions don't overlap
    const order = list.slice().sort((a, b) => a.theta - b.theta);
    for (let pass = 0; pass < 30; pass++) {
      let moved = false;
      for (let k = 0; k < order.length; k++) {
        const a = order[k], b = order[(k + 1) % order.length];
        let d = b.theta - a.theta;
        if (k === order.length - 1) d += 2 * Math.PI;
        const need = a.half + b.half;
        if (order.length > 1 && d < need) {
          const push = (need - d) / 2 + 0.001;
          a.theta -= push; b.theta += push;
          moved = true;
        }
      }
      if (!moved) break;
    }
    for (const t of list) {
      const M = t.M, Wt = t.W;
      const E = [C[0] + Math.cos(t.theta) * (r + 2), C[1] + Math.sin(t.theta) * (r + 2)];
      const L = Math.hypot(E[0] - M[0], E[1] - M[1]);
      const nUp = up(norm(-(E[1] - M[1]), E[0] - M[0]));
      const bow = Math.min(0.12 * L, 50);
      const Q = [(M[0] + E[0]) / 2 + nUp[0] * bow, (M[1] + E[1]) / 2 + nUp[1] * bow];
      const u0 = norm(Q[0] - M[0], Q[1] - M[1]);
      const tE = norm(E[0] - Q[0], E[1] - Q[1]);
      const hl = Math.min(Math.max(6, Wt * 0.5 + 4), L * 0.4), hw = Wt / 2 + Math.max(3, Wt * 0.2);
      const Eb = [E[0] - tE[0] * hl, E[1] - tE[1] * hl];
      const n0 = [-u0[1], u0[0]], n2 = [-tE[1], tE[0]];
      const n1 = norm(n0[0] + n2[0], n0[1] + n2[1]);
      t.trunk = `M${M[0]},${M[1]}Q${Q[0]},${Q[1]} ${Eb[0]},${Eb[1]}`;
      t.mid = quadAt(M, Q, Eb, 0.5);
      // lanes ordered across the bundle so branches never cross at the join
      t.branches.sort((a, b) => ((a.p0[0] - M[0]) * n0[0] + (a.p0[1] - M[1]) * n0[1]) - ((b.p0[0] - M[0]) * n0[0] + (b.p0[1] - M[1]) * n0[1]));
      let cum = -Wt / 2;
      t.heads = [];
      for (const br of t.branches) {
        br.w = br.v * kpx * t.s;
        const off = cum + br.w / 2;
        const a0 = cum, a1 = cum + br.w;
        cum += br.w;
        const P3 = [M[0] + n0[0] * off, M[1] + n0[1] * off];
        const Lb = Math.hypot(P3[0] - br.p0[0], P3[1] - br.p0[1]);
        const P2 = [P3[0] - u0[0] * Lb * 0.38, P3[1] - u0[1] * Lb * 0.38];
        const bn = up(norm(-(P3[1] - br.p0[1]), P3[0] - br.p0[0]));
        const bb = Math.min(0.14 * Lb, 70);
        const P1 = [br.p0[0] + (P3[0] - br.p0[0]) * 0.3 + bn[0] * bb, br.p0[1] + (P3[1] - br.p0[1]) * 0.3 + bn[1] * bb];
        const Q1 = [Q[0] + n1[0] * off, Q[1] + n1[1] * off];
        const E1 = [Eb[0] + n2[0] * off, Eb[1] + n2[1] * off];
        const start = Lb > 2 ? `M${br.p0[0]},${br.p0[1]}C${P1[0]},${P1[1]} ${P2[0]},${P2[1]} ${P3[0]},${P3[1]}` : `M${P3[0]},${P3[1]}`;
        br.d = `${start}Q${Q1[0]},${Q1[1]} ${E1[0]},${E1[1]}`;
        br.branchD = Lb > 2 ? `M${br.p0[0]},${br.p0[1]}C${P1[0]},${P1[1]} ${P2[0]},${P2[1]} ${P3[0]},${P3[1]}` : null;
        // this lane's slice of the arrowhead
        const f0 = a0 / Wt, f1 = a1 / Wt;
        const B0 = [Eb[0] + n2[0] * f0 * 2 * hw, Eb[1] + n2[1] * f0 * 2 * hw];
        const B1 = [Eb[0] + n2[0] * f1 * 2 * hw, Eb[1] + n2[1] * f1 * 2 * hw];
        t.heads.push({ id: br.id, d: `M${E[0]},${E[1]}L${B0[0]},${B0[1]}L${B1[0]},${B1[1]}Z` });
        br.tree = t.key;
      }
    }
    return list.sort((a, b) => a.total - b.total);
  }

  function drawMap() {
    const y = S.year;
    const i = y - Y0;
    const F = flowsAt(y);
    const approx = basisInfo(F.basis).cls !== "official";
    const dark = d3.hsl(css("--bg")).l < 0.5;
    const landC = css("--land");
    const byId = new Map(F.list.map((d) => [d.id, d]));
    const topV = F.list.length ? F.list[0].v : 1;

    // borders as they stood that year, origins tinted by region
    const pids = politiesAt(y);
    gPol.selectAll("path").data(pids, (k) => k).join("path").attr("class", "polity").attr("d", polD)
      .attr("fill", (k) => {
        const ids = originsIn(k).filter((id) => byId.has(id));
        if (!ids.length) return landC;
        const best = ids.reduce((a, b) => (byId.get(b).v > byId.get(a).v ? b : a));
        const v = d3.sum(ids, (id) => byId.get(id).v);
        const sel = S.origin && ids.includes(S.origin);
        const t = sel ? 0.55 : S.origin ? 0.06 : 0.06 + 0.3 * Math.sqrt(Math.min(1, v / topV));
        return d3.interpolateRgb(landC, color[originById[best].group])(dark ? t * 0.75 : t);
      })
      .on("pointerenter", (evt, k) => showPolityTip(evt, k, byId, approx))
      .on("pointermove", moveTip)
      .on("pointerleave", hideTip)
      .on("click", (evt, k) => {
        const ids = originsIn(k).filter((id) => byId.has(id)).sort((a, b) => byId.get(b).v - byId.get(a).v);
        if (ids.length) selectOrigin(ids[0] === S.origin ? null : ids[0]);
      });
    // the United States as it stood on July 1
    const ids = (G.usYears[y] || []).filter((k) => jurs[k].properties.type !== "other");
    gUS.selectAll("path").data(ids, (k) => k).join("path").attr("class", "us-jur").attr("d", usD);

    // the US circle: population, native-born and immigrants by birthplace
    const St = stockAt(y);
    const C = usCentre(y);
    const r = St && St.pop ? clamp(rMax * Math.sqrt(St.pop / POP_MAX), 9, rMax) : 9;
    drawDonut(y, St, C, r);
    drawDonutLabels();

    const trees = buildTrees(y, C, r);
    const dimB = (id) => (S.origin && id !== S.origin ? 0.12 : null);
    const lanes = trees.flatMap((t) => t.branches);
    const heads = trees.flatMap((t) => t.heads);
    gArrows.selectAll("path.trunk").data([]).join("path");
    gArrows.selectAll("path.branch").data(lanes, (b) => b.id).join("path").attr("class", "branch")
      .attr("d", (b) => b.d).attr("stroke", (b) => color[originById[b.id].group])
      .attr("stroke-width", (b) => Math.max(0.5, b.w))
      .attr("stroke-opacity", (b) => dimB(b.id) ?? (b.w < 1 ? 0.5 : 0.8));
    gArrows.selectAll("path.head-tri").data(heads, (h) => h.id).join("path").attr("class", "head-tri")
      .attr("d", (h) => h.d).attr("fill", (h) => color[originById[h.id].group])
      .attr("fill-opacity", (h) => dimB(h.id) ?? 0.9).raise();
    const flowing = motion ? trees.filter((t) => t.W >= 2.5) : [];
    gFlow.selectAll("path").data(flowing, (t) => t.key).join("path").attr("class", "flow")
      .attr("d", (t) => t.trunk).attr("stroke-width", (t) => Math.max(1.1, Math.min(6, t.W * 0.18)))
      .each(function (t) {
        const gap = clamp(t.W * 1.4, 12, 40);
        this.style.strokeDasharray = `0 ${gap}`;
        this.style.setProperty("--off", -gap + "px");
        this.style.setProperty("--dur", (gap / 28).toFixed(2) + "s");
      });
    gHit.selectAll("path.hit-t").data(trees, (t) => t.key).join("path").attr("class", "hit hit-t")
      .attr("d", (t) => t.trunk).attr("stroke-width", (t) => Math.max(12, t.W + 6))
      .on("pointerenter", (evt, t) => showTreeTip(evt, t, approx))
      .on("pointermove", moveTip).on("pointerleave", hideTip);
    gHit.selectAll("path.hit-b").data(lanes.filter((b) => b.branchD), (b) => b.id).join("path").attr("class", "hit hit-b")
      .attr("d", (b) => b.branchD).attr("stroke-width", (b) => Math.max(10, b.w + 6))
      .on("pointerenter", (evt, b) => showOriginTip(evt, b.id, byId, approx))
      .on("pointermove", moveTip).on("pointerleave", hideTip)
      .on("click", (evt, b) => selectOrigin(S.origin === b.id ? null : b.id));
    last = { F, approx, C, r, St, y };
    drawLabels();
    drawKey(y, trees, F);
  }

  function drawDonut(y, St, C, r) {
    gDonut.attr("transform", `translate(${C[0]},${C[1]})`);
    const segs = [];
    if (St && St.pop) {
      const fb = Math.min(St.total, St.pop);
      segs.push({ id: "_native", v: Math.max(0, St.pop - fb), c: css("--native") });
      const list = [...St.m].map(([id, v]) => ({ id, v })).sort((a, b) => {
        const ga = groups.findIndex((g) => g.id === originById[a.id].group), gb = groups.findIndex((g) => g.id === originById[b.id].group);
        return ga - gb || b.v - a.v;
      });
      let known = 0;
      for (const d of list) { segs.push({ id: d.id, v: d.v, c: color[originById[d.id].group] }); known += d.v; }
      if (fb - known > 1) segs.push({ id: "_rest", v: fb - known, c: css("--s9") });
    }
    const pie = d3.pie().sort(null).value((d) => d.v).startAngle(0).endAngle(2 * Math.PI);
    const arc = d3.arc().innerRadius(r * 0.52).outerRadius(r);
    const arcs = segs.length ? pie(segs) : [];
    gDonut.selectAll("path").data(arcs, (a) => a.data.id).join("path").attr("d", arc)
      .attr("fill", (a) => a.data.c)
      .attr("fill-opacity", (a) => (S.origin && a.data.id !== S.origin && a.data.id !== "_native" ? 0.35 : 1))
      .on("pointerenter", (evt, a) => showDonutTip(evt, a.data, St))
      .on("pointermove", moveTip).on("pointerleave", hideTip)
      .on("click", (evt, a) => {
        if (originById[a.data.id]) selectOrigin(S.origin === a.data.id ? null : a.data.id);
        else if (zt.k < 2) zoomToUS();
      });
    gDonut.selectAll("circle.ring").data(segs.length ? [] : [0]).join("circle").attr("class", "ring").attr("r", r);
    donutArcs = { arcs, r, St, y };
  }
  let donutArcs = null;
  // caption above the circle, and slice labels once the circle is large on screen; sizes are
  // divided by the zoom so text stays the same size while the circle grows
  function drawDonutLabels() {
    if (!donutArcs) return;
    const { arcs, r, St, y } = donutArcs;
    const k = zt.k;
    const name = y < 1776 ? "Colonies" : "United States";
    const cap = St && St.pop ? [`${name} · ${compact(St.pop)}`, `${pct(Math.min(St.total, St.pop) / St.pop)} born abroad${St.kind === "model" ? " (modelled)" : ""}`] : [name, ""];
    const t = gDonut.selectAll("text.donut-label").data([0]).join((enter) => {
      const tx = enter.append("text").attr("class", "donut-label").attr("text-anchor", "middle");
      tx.append("tspan").attr("class", "n");
      tx.append("tspan").attr("class", "v");
      return tx;
    });
    t.attr("y", -r - 20 / k).style("font-size", 11.5 / k + "px").style("stroke-width", 3 / k + "px");
    t.select("tspan.n").attr("x", 0).text(cap[0]);
    t.select("tspan.v").attr("x", 0).attr("dy", "1.15em").text(cap[1]);
    const onScreen = r * k;
    const total = St && St.pop ? St.pop : 1;
    const want = onScreen < 70 ? [] : arcs.filter((a) => a.endAngle - a.startAngle > (onScreen > 160 ? 0.05 : 0.12));
    // outside labels, kept apart vertically on each side
    const placed = { l: [], r: [] };
    const fs = 10.5 / k, gap = 12.5 / k;
    const out = [];
    for (const a of want.sort((p, q) => (q.endAngle - q.startAngle) - (p.endAngle - p.startAngle))) {
      const mid = (a.startAngle + a.endAngle) / 2;
      const x = Math.sin(mid) * (r + 6 / k), yy = -Math.cos(mid) * (r + 6 / k);
      const side = x >= 0 ? "r" : "l";
      if (placed[side].some((py) => Math.abs(py - yy) < gap)) continue;
      placed[side].push(yy);
      const nm = a.data.id === "_native" ? "Born in the US" : a.data.id === "_rest" ? "Other, not broken down" : originById[a.data.id].short || originById[a.data.id].name;
      out.push({ id: a.data.id, x, y: yy, side, text: `${nm} ${pct(a.data.v / total)}` });
    }
    gDonut.selectAll("text.slice").data(out, (d) => d.id).join("text").attr("class", "slice")
      .attr("x", (d) => d.x).attr("y", (d) => d.y).attr("dy", "0.35em")
      .attr("text-anchor", (d) => (d.side === "r" ? "start" : "end"))
      .style("font-size", fs + "px").style("stroke-width", 3 / k + "px").text((d) => d.text);
  }

  function drawLabels() {
    const { F, approx, C, r } = last;
    const k = zt.k;
    const cands = F.list.filter((d, j) => originById[d.id].at && !originById[d.id].residual && (j < 3 || d.v >= (k > 2 ? 0.002 : 0.015) * (F.total || 0)));
    const order = S.origin ? cands.filter((c) => c.id === S.origin).concat(cands.filter((c) => c.id !== S.origin)) : cands;
    const max = Math.round((W < 640 ? 3 : 8) * Math.min(5, k));
    const sc = zt.apply(C);
    const placed = [[sc[0] - 70, sc[1] - r * k - 34, sc[0] + 70, sc[1] + r * k]]; // keep clear of the US circle and its caption
    const out = [];
    for (const c of order) {
      if (out.length >= max) break;
      const o = originById[c.id];
      const p = proj(o.at);
      if (!p) continue;
      const q = zt.apply(p);
      const name = o.short || o.name;
      const val = fmtCount(c.v, approx || c.un > 0);
      const wpx = Math.max(name.length * 6.6, val.length * 6) + 6;
      const box = [q[0] - wpx / 2, q[1] - 30, q[0] + wpx / 2, q[1] - 4];
      if (box[0] < 0 || box[2] > W || box[1] < 0 || box[3] > H) continue;
      if (placed.some((z) => !(box[2] < z[0] || box[0] > z[2] || box[3] < z[1] || box[1] > z[3]))) continue;
      placed.push(box);
      out.push({ id: c.id, x: p[0], y: p[1], name, val });
    }
    const t = gLabels.selectAll("text").data(out, (d) => d.id).join((enter) => {
      const tx = enter.append("text").attr("class", "label").attr("text-anchor", "middle");
      tx.append("tspan").attr("class", "n");
      tx.append("tspan").attr("class", "v");
      return tx;
    });
    t.attr("x", (d) => d.x).attr("y", (d) => d.y - 18 / k).style("font-size", 11.5 / k + "px").style("stroke-width", 3 / k + "px");
    t.select("tspan.n").attr("x", (d) => d.x).text((d) => d.name);
    t.select("tspan.v").attr("x", (d) => d.x).attr("dy", "1.15em").text((d) => d.val);
  }

  function drawKey(y, trees, F) {
    const key = $("map-key");
    key.replaceChildren();
    const wk = el("span", "wkey");
    const top = S.widthScale === "year" ? d3.max(trees, (t) => t.total) || 1 : MAXT;
    const kpx = wMax / top;
    const samples = [1e3, 1e4, 1e5, 1e6].filter((v) => v * kpx >= 0.8 && v <= top * 1.2).slice(-3);
    const ns = "http://www.w3.org/2000/svg";
    const s = document.createElementNS(ns, "svg");
    const maxw = samples.length ? Math.max(1, samples[samples.length - 1] * kpx) : 2;
    let x = 0;
    for (const v of samples) {
      const w = Math.max(1, v * kpx);
      const ln = document.createElementNS(ns, "line");
      ln.setAttribute("x1", x); ln.setAttribute("x2", x + 34);
      ln.setAttribute("y1", maxw / 2 + 1); ln.setAttribute("y2", maxw / 2 + 1);
      ln.setAttribute("stroke", css("--ink-2"));
      ln.setAttribute("stroke-width", w);
      const tx = document.createElementNS(ns, "text");
      tx.setAttribute("x", x + 17); tx.setAttribute("y", maxw + 14); tx.setAttribute("text-anchor", "middle");
      tx.textContent = compact(v);
      s.append(ln, tx);
      x += 52;
    }
    s.setAttribute("width", Math.max(1, x - 18));
    s.setAttribute("height", maxw + 17);
    s.setAttribute("aria-hidden", "true");
    wk.append(el("span", null, "Arrow width: people arriving"), s);
    key.append(wk);
    const seg = el("span", "seg seg-sm");
    seg.setAttribute("role", "group");
    seg.setAttribute("aria-label", "Arrow width scale");
    for (const [k, label] of [["all", "Same scale every year"], ["year", "Fit to " + y]]) {
      const b = el("button", null, label);
      b.type = "button";
      b.setAttribute("aria-pressed", String(S.widthScale === k));
      b.addEventListener("click", () => { S.widthScale = k; drawMap(); });
      seg.append(b);
    }
    key.append(seg);
    const notes = [];
    if (trees.some((t) => t.forced > 0)) notes.push("Arrows from Africa carry enslaved people brought by force.");
    if (F.un > 0) notes.push("Widths include estimated illegal immigration.");
    notes.push("The circle is the US population: grey born in the US, colors born abroad by birthplace.");
    notes.push("Drag to pan; pinch, Ctrl/⌘ + scroll or double-click to zoom.");
    key.append(el("span", "note", notes.join(" ")));
  }

  function showOriginTip(evt, id, byId, approx) {
    const o = originById[id];
    const d = byId.get(id);
    const F = flowsAt(S.year);
    showTip(evt, (t) => {
      t.append(el("h4", null, o.name));
      if (!d) { t.append(el("div", "note", `No arrivals recorded in ${S.year}.`)); return; }
      if (o.forced) tipRow(t, color[o.group], "Enslaved people landed", fmtCount(d.v, true));
      else {
        tipRow(t, color[o.group], d.un ? "Arrived legally" : "Arrived in " + S.year, fmtCount(d.legal, approx));
        if (d.un) tipRow(t, null, "Illegal (estimate)", fmtCount(d.un, true));
      }
      if (F.total) t.append(el("div", "note", pct(d.v / F.total) + " of all arrivals in " + S.year));
      if (o.note) t.append(el("div", "note", o.note));
    });
  }
  function showTreeTip(evt, tr, approx) {
    showTip(evt, (t) => {
      t.append(el("h4", null, treeName(tr.key)));
      tipRow(t, null, "Arrivals in " + S.year, fmtCount(tr.total, approx || tr.un > 0));
      if (tr.forced) t.append(el("div", "note", `Including ${fmtInt(roundEst(tr.forced))} enslaved people brought by force.`));
      if (tr.un) t.append(el("div", "note", `Including an estimated ${fmtInt(roundEst(tr.un))} illegal immigrants.`));
      for (const b of tr.branches.slice().sort((a, b2) => b2.v - a.v).slice(0, 6)) tipRow(t, color[originById[b.id].group], originById[b.id].name, fmtCount(b.v, approx || b.un > 0));
    });
  }
  function showPolityTip(evt, k, byId, approx) {
    const p = polities[k].properties;
    showTip(evt, (t) => {
      t.append(el("h4", null, p.name || p.ne_name || "—"));
      if (p.sub && p.sub !== p.name) t.append(el("div", "note", "Under " + p.sub));
      const ids = originsIn(k).filter((id) => byId.has(id)).sort((a, b) => byId.get(b).v - byId.get(a).v);
      if (!ids.length) { t.append(el("div", "note", `No arrivals recorded from here in ${S.year}.`)); return; }
      for (const id of ids.slice(0, 6)) {
        const d = byId.get(id);
        tipRow(t, color[originById[id].group], originById[id].name, fmtCount(d.v, approx || d.un > 0));
      }
    });
  }
  function showDonutTip(evt, seg, St) {
    showTip(evt, (t) => {
      if (seg.id === "_native") t.append(el("h4", null, "Born in the US (or its colonies)"));
      else if (seg.id === "_rest") t.append(el("h4", null, "Born abroad, birthplace not broken down"));
      else t.append(el("h4", null, "Born in " + originById[seg.id].name));
      const approx = St.kind !== "census" && St.kind !== "acs";
      tipRow(t, seg.c, "Residents in " + S.year, fmtCount(seg.v, approx));
      t.append(el("div", "note", pct(seg.v / St.pop) + " of the population" + (seg.id === "_native" ? "" : `, ${pct(seg.v / St.total)} of immigrants`)));
      if (St.kind === "model") t.append(el("div", "note", `Modelled: birthplace was first recorded in the ${STOCK_FIRST} census. Excludes most Native Americans.`));
      else if (St.kind === "interp") t.append(el("div", "note", `Interpolated between the ${St.a} and ${St.b} counts.`));
      else if (St.kind === "cps") t.append(el("div", "note", "Monthly survey estimate (CPS), preliminary."));
    });
  }

  // ---------- region chart ----------
  const chartBox = $("chart");
  let chart = null;
  const keysFor = (series) => (series === "flow" ? groups.flatMap((g) => (HAS_UN ? [g.id, g.id + "~u"] : [g.id])) : groups.map((g) => g.id));
  function layoutChart() {
    const Wd = Math.max(320, chartBox.clientWidth || 1200);
    const Ht = Wd < 640 ? 210 : 260;
    const m = { t: 18, r: 6, b: 24, l: 44 };
    chartBox.replaceChildren();
    const s = d3.select(chartBox).append("svg").attr("viewBox", `0 0 ${Wd} ${Ht}`).attr("role", "img");
    const defs = s.append("defs");
    for (const g of groups) {
      const p = defs.append("pattern").attr("id", "hatch-" + g.id).attr("patternUnits", "userSpaceOnUse").attr("width", 5).attr("height", 5).attr("patternTransform", "rotate(45)");
      p.append("rect").attr("width", 5).attr("height", 5).attr("class", "hatch-bg");
      p.append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 5).attr("class", "hatch-line").attr("data-g", g.id).attr("stroke-width", 2.2);
    }
    const x = d3.scaleLinear().domain([Y0, Y1]).range([m.l, Wd - m.r]);
    chart = { s, Wd, Ht, m, x, gGrid: s.append("g").attr("class", "grid"), gArea: s.append("g"), gAxis: s.append("g").attr("class", "axis"), gBand: s.append("g").attr("class", "band"), gEv: s.append("g") };
    chart.hover = s.append("line").attr("class", "hover-line").attr("y1", m.t).attr("y2", Ht - m.b).attr("visibility", "hidden");
    chart.cursor = s.append("line").attr("class", "cursor").attr("y1", m.t).attr("y2", Ht - m.b);
    const overlay = s.append("rect").attr("x", m.l).attr("y", 0).attr("width", Wd - m.l - m.r).attr("height", Ht).attr("fill", "transparent");
    const yearAt = (evt) => clamp(Math.round(x.invert(d3.pointer(evt, s.node())[0])), Y0, Y1);
    overlay
      .on("click", (evt) => { stopPlay(); setYear(yearAt(evt)); })
      .on("pointermove", (evt) => {
        const yy = yearAt(evt);
        chart.hover.attr("visibility", "visible").attr("x1", x(yy)).attr("x2", x(yy));
        showChartTip(evt, yy);
      })
      .on("pointerleave", () => { chart.hover.attr("visibility", "hidden"); hideTip(); });
    drawChart();
  }
  function drawChart() {
    if (!chart) return;
    const { s, Wd, Ht, m, x, gGrid, gArea, gAxis, gBand, gEv } = chart;
    s.selectAll(".hatch-bg").attr("fill", css("--bg"));
    s.selectAll(".hatch-line").attr("stroke", function () { return color[this.getAttribute("data-g")]; });
    const data = S.series === "flow" ? flowGroups : stockGroups;
    const keys = keysFor(S.series);
    const series = d3.stack().keys(keys).offset(S.chartScale === "share" ? d3.stackOffsetExpand : d3.stackOffsetNone)(data);
    const ymax = S.chartScale === "share" ? 1 : d3.max(series[series.length - 1], (d) => d[1]) || 1;
    const y = d3.scaleLinear().domain([0, ymax]).range([Ht - m.b, m.t]).nice();
    const area = d3.area().curve(d3.curveMonotoneX).x((d) => x(d.data.year))
      .y0((d) => (isNaN(d[0]) ? y(0) : y(d[0]))).y1((d) => (isNaN(d[1]) ? y(0) : y(d[1])));
    gArea.selectAll("path").data(series, (d) => d.key).join("path").attr("d", area)
      .attr("fill", (d) => (d.key.endsWith("~u") ? `url(#hatch-${d.key.slice(0, -2)})` : color[d.key]))
      .attr("fill-opacity", 0.92);
    const yt = S.chartScale === "share" ? [0, 0.25, 0.5, 0.75, 1] : y.ticks(4);
    gGrid.selectAll("line").data(yt).join("line").attr("x1", m.l).attr("x2", Wd - m.r).attr("y1", (d) => y(d)).attr("y2", (d) => y(d));
    gAxis.selectAll("*").remove();
    gAxis.selectAll("text.yt").data(yt).join("text").attr("class", "yt").attr("x", m.l - 6).attr("y", (d) => y(d)).attr("dy", "0.32em").attr("text-anchor", "end")
      .text((d) => (S.chartScale === "share" ? Math.round(d * 100) + "%" : compact(d)));
    const ticks = Wd < 640 ? [1650, 1750, 1850, 1950] : [1607, 1650, 1700, 1750, 1800, 1850, 1900, 1950, 2000, Y1];
    gAxis.selectAll("text.xt").data(ticks).join("text").attr("class", "xt").attr("x", (d) => x(d)).attr("y", Ht - 6)
      .attr("text-anchor", (d) => (d === Y0 ? "start" : d === Y1 ? "end" : "middle")).text((d) => d);
    gBand.selectAll("*").remove();
    const firstOfficial = S.series === "flow" ? Y0 + D.flow.basis.search(/[HDAB]/) : STOCK_FIRST;
    gBand.append("line").attr("x1", x(Y0)).attr("x2", x(firstOfficial)).attr("y1", 6).attr("y2", 6).attr("stroke", css("--muted")).attr("stroke-dasharray", "1 3");
    gBand.append("line").attr("x1", x(firstOfficial)).attr("x2", x(Y1)).attr("y1", 6).attr("y2", 6).attr("stroke", css("--muted"));
    if (Wd > 560) {
      gBand.append("text").attr("x", x(Y0)).attr("y", 2).text(S.series === "flow" ? "Estimates" : "Modelled from arrivals");
      gBand.append("text").attr("x", x(firstOfficial) + 4).attr("y", 2).text(S.series === "flow" ? "Official counts" : "Census and surveys");
    }
    gEv.selectAll("*").remove();
    for (const e of D.events) gEv.append("line").attr("class", "event-tick").attr("x1", x(e.y)).attr("x2", x(e.y)).attr("y1", Ht - m.b).attr("y2", Ht - m.b + 4);
    $("chart-title").textContent = S.series === "flow" ? `Arrivals by region of origin, ${Y0}–${Y1}` : `Immigrants living in the US by region of birth, ${Y0}–${Y1}`;
    s.attr("aria-label", $("chart-title").textContent + (S.chartScale === "share" ? ", share" : ", number of people"));
    const leg = $("legend");
    leg.replaceChildren();
    for (const g of groups) {
      const sp = el("span");
      const b = el("b");
      b.style.background = color[g.id];
      sp.append(b, document.createTextNode(g.name));
      leg.append(sp);
    }
    if (HAS_UN && S.series === "flow") {
      const sp = el("span");
      const ns = "http://www.w3.org/2000/svg";
      const sv = document.createElementNS(ns, "svg");
      sv.setAttribute("width", 10); sv.setAttribute("height", 10);
      const rc = document.createElementNS(ns, "rect");
      rc.setAttribute("width", 10); rc.setAttribute("height", 10); rc.setAttribute("rx", 2);
      rc.setAttribute("fill", "url(#hatch-see)");
      sv.append(rc);
      sp.append(sv, document.createTextNode("Hatched: illegal immigration (estimated)"));
      leg.append(sp);
    }
    moveCursor();
  }
  function moveCursor() {
    if (chart) chart.cursor.attr("x1", chart.x(S.year)).attr("x2", chart.x(S.year));
  }
  function showChartTip(evt, yy) {
    const row = S.series === "flow" ? flowGroups[yy - Y0] : stockGroups[yy - Y0];
    const ev = D.events.filter((e) => e.y === yy);
    showTip(evt, (t) => {
      t.append(el("h4", null, String(yy)));
      for (const e of ev) t.append(el("div", "note", e.title));
      const tot = d3.sum(keysFor(S.series), (k) => row[k] || 0);
      if (!tot) { t.append(el("div", "note", S.series === "flow" ? "No arrivals recorded." : "No estimate.")); return; }
      for (const g of [...groups].reverse()) {
        const v = row[g.id] + (row[g.id + "~u"] || 0);
        if (v > 0) tipRow(t, color[g.id], g.name, (S.chartScale === "share" ? pct(v / tot) + " · " : "") + compact(v));
      }
      const un = S.series === "flow" ? d3.sum(groups, (g) => row[g.id + "~u"] || 0) : 0;
      t.append(el("div", "note", (S.series === "flow" ? "Arrivals: " : "Born abroad: ") + fmtInt(Math.round(tot)) + (un ? ` (≈${fmtInt(roundEst(un))} illegal)` : "") + ". Click to go to " + yy + "."));
    });
  }

  // ---------- origins list ----------
  function drawList() {
    const y = S.year;
    const F = flowsAt(y);
    const approx = basisInfo(F.basis).cls !== "official";
    $("o-year").textContent = y;
    const list = $("olist");
    list.replaceChildren();
    const q = S.query.trim().toLowerCase();
    let rows = F.list;
    if (q) {
      const present = new Map(F.list.map((d) => [d.id, d]));
      rows = origins.filter((o) => o.name.toLowerCase().includes(q)).map((o) => present.get(o.id) || { id: o.id, v: 0, legal: 0, un: 0 }).sort((a, b) => b.v - a.v);
    }
    const shown = q || S.showAll ? rows : rows.slice(0, 10);
    if (!shown.length) list.append(el("li", "empty", q ? "No origin matches that search." : "No arrivals recorded this year."));
    const max = F.list.length ? F.list[0].v : 1;
    for (const d of shown) {
      const o = originById[d.id];
      const li = el("li");
      const b = el("button", "orow");
      b.type = "button";
      b.setAttribute("aria-pressed", String(S.origin === d.id));
      if (d.un) b.title = `${fmtCount(d.legal, approx)} legal, ≈${fmtInt(roundEst(d.un))} illegal (estimate)`;
      const vl = el("span", "vl", d.v ? fmtCount(d.v, approx || d.un > 0) : "–");
      if (d.v && F.total) vl.append(el("small", null, pct(d.v / F.total)));
      const bar = el("span", "bar");
      const i1 = el("i");
      i1.style.width = (100 * d.legal) / max + "%";
      i1.style.background = color[o.group];
      bar.append(i1);
      if (d.un) {
        const i2 = el("i");
        i2.style.width = (100 * d.un) / max + "%";
        i2.style.background = `repeating-linear-gradient(135deg, ${color[o.group]} 0 2px, transparent 2px 4px)`;
        bar.append(i2);
      }
      b.append(el("span", "nm", o.name), vl, bar);
      b.addEventListener("click", () => selectOrigin(S.origin === d.id ? null : d.id));
      li.append(b);
      list.append(li);
    }
    const more = $("more");
    more.hidden = F.list.length <= 10 && !S.showAll;
    more.textContent = S.showAll ? "Top 10" : `All ${F.list.length} origins`;
    $("o-search").hidden = !S.showAll;
    drawDetail();
  }
  function drawDetail() {
    const box = $("detail");
    if (!S.origin) { box.hidden = true; return; }
    const o = originById[S.origin];
    box.hidden = false;
    box.replaceChildren();
    const head = el("div", "d-head");
    const h = el("h3");
    const k = el("i");
    k.style.background = color[o.group];
    h.append(k, document.createTextNode(o.name));
    const clr = el("button", "link", "Clear");
    clr.type = "button";
    clr.addEventListener("click", () => selectOrigin(null));
    head.append(h, clr);
    box.append(head);
    const arr = Array.from({ length: NY }, (_, i) => legalAt(o.id, i) + unAt(o.id, i));
    let peak = 0, peakY = null, total = 0;
    arr.forEach((v, i) => { total += v; if (v > peak) { peak = v; peakY = Y0 + i; } });
    const St = stockAt(S.year);
    const nat = St ? St.m.get(o.id) : null;
    let txt = peakY ? `Most arrivals in one year: ${fmtInt(Math.round(peak))} in ${peakY}. ${fmtInt(Math.round(total))} in all since ${Y0}.` : "No arrivals recorded.";
    if (nat) txt += ` ${St.kind === "census" || St.kind === "acs" ? "" : "About "}${fmtInt(Math.round(nat))} people born here lived in the US in ${S.year}.`;
    if (o.note) txt += " " + o.note;
    box.append(el("p", null, txt));
    const Wd = Math.max(260, box.clientWidth - 28), Ht = 64;
    const x = d3.scaleLinear().domain([Y0, Y1]).range([0, Wd]);
    const yS = d3.scaleLinear().domain([0, peak || 1]).range([Ht - 2, 4]);
    const s = d3.create("svg").attr("viewBox", `0 0 ${Wd} ${Ht}`).attr("aria-label", `Arrivals from ${o.name} by year`);
    const pts = arr.map((v, i) => [Y0 + i, v]);
    s.append("path").attr("d", d3.area().x((d) => x(d[0])).y0(Ht - 2).y1((d) => yS(d[1]))(pts)).attr("fill", color[o.group]).attr("fill-opacity", 0.18);
    s.append("path").attr("d", d3.line().x((d) => x(d[0])).y((d) => yS(d[1]))(pts)).attr("fill", "none").attr("stroke", color[o.group]).attr("stroke-width", 1.5);
    s.append("line").attr("x1", x(S.year)).attr("x2", x(S.year)).attr("y1", 0).attr("y2", Ht).attr("stroke", css("--ink")).attr("stroke-width", 1);
    box.append(s.node());
  }
  function selectOrigin(id) {
    S.origin = id;
    drawMap();
    drawList();
  }

  // ---------- headline ----------
  function currentEvent(y, within) {
    let best = null;
    for (const e of D.events) if (e.y <= y && y - e.y <= within && (!best || e.y >= best.y)) best = e;
    return best;
  }
  function drawHeadline() {
    const y = S.year;
    $("year").textContent = y;
    $("scrub-year").textContent = y;
    const F = flowsAt(y);
    const bi = basisInfo(F.basis);
    const est = bi.cls === "estimate";
    const lede = $("lede");
    lede.replaceChildren();
    const txt = (t) => lede.append(document.createTextNode(t));
    const strong = (t) => lede.append(el("strong", null, t));
    if (F.total) {
      if (F.un > 0) {
        txt("About ");
        strong(fmtInt(roundEst(F.total)));
        txt(` people arrived in ${y}: `);
        txt(F.legal ? `${fmtInt(est ? roundEst(F.legal) : F.legal)} legally and an estimated ${fmtInt(roundEst(F.un))} illegally. ` : `an estimated ${fmtInt(roundEst(F.un))} illegally (legal arrivals not yet published). `);
      } else {
        const n = est ? roundEst(F.total) : F.total;
        txt(est ? "About " : "");
        strong(fmtInt(n));
        txt(` ${n === 1 ? "person" : "people"} arrived in ${y}. `);
      }
      const named = F.list.filter((d) => !originById[d.id].residual).slice(0, 2);
      if (named.length) {
        txt(named[1] ? "Largest origins: " : "Largest origin: ");
        strong(originById[named[0].id].name);
        txt(` (${pct(named[0].v / F.total)})`);
        if (named[1]) { txt(", "); strong(originById[named[1].id].name); txt(` (${pct(named[1].v / F.total)})`); }
        txt(". ");
      }
      const forced = F.list.filter((d) => originById[d.id].forced).reduce((s, d) => s + d.v, 0);
      if (forced > 0) txt(`About ${fmtInt(roundEst(forced))} were enslaved Africans brought by force. `);
    } else {
      txt(`Arrivals for ${y} haven't been published yet. `);
    }
    const St = stockAt(y);
    if (St && St.pop) { txt(St.kind === "census" || St.kind === "acs" ? "" : "About "); strong(pct(Math.min(St.total, St.pop) / St.pop)); txt(" of residents were born abroad."); }
    const b = $("basis");
    b.className = "basis " + bi.cls;
    b.replaceChildren(el("i"), document.createTextNode(bi.label + (F.un > 0 ? " · illegal immigration estimated" : "")));
    b.title = bi.long || "";
    const ev = currentEvent(y, 12);
    const ctx = $("context");
    ctx.replaceChildren();
    if (ev) { ctx.append(el("b", null, `${ev.y} · ${ev.title}. `), document.createTextNode(ev.t)); ctx.title = `${ev.y} · ${ev.title}. ${ev.t}`; }
    else ctx.title = "";
  }

  // ---------- about ----------
  function drawAbout() {
    const box = $("about-body");
    for (const p of D.about.intro) box.append(el("p", null, p));
    const ts = el("div", "table-scroll");
    const table = el("table");
    const hr = el("tr");
    for (const h of ["Years", "Arrivals by origin", "Immigrants living here"]) hr.append(el("th", null, h));
    const thead = el("thead");
    thead.append(hr);
    const tb = el("tbody");
    for (const e of D.eras) {
      const tr = el("tr");
      tr.append(el("td", null, e.years), el("td", null, e.flow), el("td", null, e.stock));
      tb.append(tr);
    }
    table.append(thead, tb);
    ts.append(table);
    box.append(ts);
    box.append(el("h3", null, "Caveats"));
    const ul = el("ul");
    for (const c of D.about.caveats) ul.append(el("li", null, c));
    box.append(ul);
    const det = el("details");
    det.append(el("summary", null, `Sources (${D.sources.length})`));
    const ul2 = el("ul");
    for (const s of D.sources) {
      const li = el("li", null, s.cite + " ");
      if (s.url) {
        const a = el("a", null, s.url.replace(/^https?:\/\//, "").replace(/\/$/, ""));
        a.href = s.url;
        a.target = "_blank";
        a.rel = "noopener";
        li.append(a);
      }
      ul2.append(li);
    }
    det.append(ul2);
    box.append(det);
  }

  // ---------- controls ----------
  let drawn = false;
  function setYear(y) {
    y = clamp(y, Y0, Y1);
    if (y === S.year && drawn) return;
    S.year = y;
    $("slider").value = y;
    try { history.replaceState(null, "", "#" + y); } catch (e) { /* sandboxed frame */ }
    drawAll();
  }
  function drawAll() {
    drawHeadline();
    drawMap();
    moveCursor();
    drawList();
    drawn = true;
  }
  function stopPlay() {
    if (!S.playing) return;
    S.playing = false;
    clearInterval(S.timer);
    $("play").setAttribute("aria-pressed", "false");
    $("play").setAttribute("aria-label", "Play");
    $("play-icon").setAttribute("d", "M4.5 2.5v11l9-5.5z");
  }
  function startPlay() {
    if (S.year >= Y1) setYear(Y0);
    S.playing = true;
    $("play").setAttribute("aria-pressed", "true");
    $("play").setAttribute("aria-label", "Pause");
    $("play-icon").setAttribute("d", "M4 2.5h3v11H4zM9 2.5h3v11H9z");
    S.timer = setInterval(() => (S.year >= Y1 ? stopPlay() : setYear(S.year + 1)), 140);
  }
  function drawTicks() {
    const box = $("ticks");
    box.replaceChildren();
    const marks = (box.clientWidth || 600) < 520 ? [1607, 1700, 1800, 1900, Y1] : [1607, 1650, 1700, 1750, 1800, 1850, 1900, 1950, 2000, Y1];
    for (const t of marks) {
      const s = el("span", null, t);
      const f = (t - Y0) / (Y1 - Y0);
      s.style.left = `calc(${f * 100}% + ${(0.5 - f) * 16}px)`;
      if (t === Y0) s.style.transform = "translateX(-8px)";
      if (t === Y1) s.style.transform = "translateX(calc(-100% + 8px))";
      box.append(s);
    }
  }
  $("play").addEventListener("click", () => (S.playing ? stopPlay() : startPlay()));
  $("slider").addEventListener("input", (e) => { stopPlay(); setYear(+e.target.value); });
  $("q").addEventListener("input", (e) => { S.query = e.target.value; drawList(); });
  $("more").addEventListener("click", () => { S.showAll = !S.showAll; if (!S.showAll) S.query = ""; $("q").value = S.query; drawList(); });
  const segToggle = (id, attr, apply) => $(id).addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    for (const x of $(id).querySelectorAll("button")) x.setAttribute("aria-pressed", String(x === b));
    apply(b.dataset[attr]);
  });
  segToggle("series", "series", (v) => { S.series = v; drawChart(); });
  segToggle("scale", "scale", (v) => { S.chartScale = v; drawChart(); });
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, select")) return;
    if (e.key === "ArrowRight") { stopPlay(); setYear(S.year + (e.shiftKey ? 10 : 1)); e.preventDefault(); }
    else if (e.key === "ArrowLeft") { stopPlay(); setYear(S.year - (e.shiftKey ? 10 : 1)); e.preventDefault(); }
    else if (e.key === " " && !e.target.closest("button, summary, a")) { S.playing ? stopPlay() : startPlay(); e.preventDefault(); }
    else if (e.key === "Escape" && S.origin) selectOrigin(null);
  });

  const onTheme = () => { readColors(); drawChart(); drawAll(); };
  try { matchMedia("(prefers-color-scheme: dark)").addEventListener("change", onTheme); } catch (e) { /* old browsers */ }
  new MutationObserver(onTheme).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  let rT = null, lastW = document.documentElement.clientWidth;
  window.addEventListener("resize", () => {
    clearTimeout(rT);
    rT = setTimeout(() => {
      if (Math.abs(document.documentElement.clientWidth - lastW) < 4) return;
      lastW = document.documentElement.clientWidth;
      layoutMap(); layoutChart(); drawTicks(); drawAll();
    }, 150);
  });

  // ---------- boot ----------
  $("y-start").textContent = Y0;
  $("y-end").textContent = Y1;
  const sl = $("slider");
  sl.min = Y0; sl.max = Y1; sl.value = S.year;
  layoutMap();
  layoutChart();
  drawTicks();
  drawAbout();
  drawAll();
})();
