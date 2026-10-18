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
  const compact = (n) => (n == null ? "—" : n < 1000 ? String(Math.round(n)) : compactFmt.format(n));
  const pct = (x) => (x == null ? "—" : x < 0.005 ? "<1%" : x < 0.1 ? (x * 100).toFixed(1) + "%" : Math.round(x * 100) + "%");
  const roundEst = (n) => (n < 100 ? Math.round(n) : n < 1000 ? Math.round(n / 10) * 10 : n < 100000 ? Math.round(n / 100) * 100 : Math.round(n / 1000) * 1000);
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

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
    for (let i = 0; i < vals.length; i++) a[s + i] = vals[i] || 0;
    return a;
  };
  const flowBy = {};
  for (const [id, sp] of Object.entries(D.flow.o)) flowBy[id] = expand(sp);
  const flowIds = Object.keys(flowBy);
  const forcedBy = {}; // origin id -> [{land, a}]
  for (const [id, lands] of Object.entries(D.forced.pairs)) {
    forcedBy[id] = Object.entries(lands).map(([land, sp]) => ({ land, a: expand(sp) }));
  }

  const flowGroups = [];
  for (let i = 0; i < NY; i++) {
    const row = { year: Y0 + i };
    for (const g of groups) row[g.id] = 0;
    for (const id of flowIds) if (flowBy[id][i]) row[originById[id].group] += flowBy[id][i];
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
  const stockGroups = [];
  for (let y = Y0; y <= Y1; y++) {
    const row = { year: y };
    for (const g of groups) {
      const r = y >= STOCK_FIRST ? interp(D.stock.nat.g[g.id], y) : null;
      row[g.id] = r ? r.v : 0;
    }
    stockGroups.push(row);
  }

  function flowsAt(y) {
    const i = y - Y0;
    const list = [];
    for (const id of flowIds) if (flowBy[id][i] > 0) list.push({ id, v: flowBy[id][i] });
    list.sort((a, b) => b.v - a.v);
    return { list, total: D.flow.total[i], basis: D.flow.basis[i] };
  }

  // ---------- state ----------
  const hashYear = parseInt((location.hash || "").replace("#", ""), 10);
  const S = {
    year: hashYear >= Y0 && hashYear <= Y1 ? hashYear : D.defaultYear || 1910,
    origin: null,
    series: "flow",
    scale: "all",
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
  const fmtCount = (v, approx) => (approx ? "≈" + fmtInt(roundEst(v)) : fmtInt(Math.round(v)));

  // ---------- world flow map ----------
  // Centred on 90°W so Europe and Africa sit east of the US and East Asia west, across the Pacific.
  const MAP_ROTATE = 90;
  const countries = topojson.feature(G.world, G.world.objects.countries).features.filter((f) => f.properties.iso3 !== "ATA");
  const land = { type: "FeatureCollection", features: countries };
  const jurs = topojson.feature(G.us, G.us.objects.jurisdictions).features;
  const PORTS = {
    east: (y) => (y < 1700 ? [-76.3, 37.1] : y < 1820 ? [-75.15, 39.95] : [-74.0, 40.7]),
    florida: (y) => (y < 1900 ? PORTS.east(y) : [-80.2, 25.8]),
    border: () => [-99.0, 29.6],
    west: () => [-122.4, 37.8],
    north: () => [-83.05, 42.33],
  };
  const COAST_NAME = { east: "East Coast", florida: "Florida", border: "Mexican border", west: "West Coast", north: "Canadian border" };

  // one width scale for every year: the widest arrow is the largest single flow in the record
  let MAXV = 0;
  for (const id of flowIds) {
    if (forcedBy[id]) continue;
    for (const v of flowBy[id]) if (v > MAXV) MAXV = v;
  }
  for (const id in forcedBy) for (const p of forcedBy[id]) for (const v of p.a) if (v > MAXV) MAXV = v;

  const mapBox = $("map");
  const svg = d3.select(mapBox).append("svg");
  const gLand = svg.append("g");
  const gUS = svg.append("g");
  const gArrows = svg.append("g");
  const gFlow = svg.append("g");
  const gPorts = svg.append("g");
  const gLabels = svg.append("g");
  const gHit = svg.append("g");
  let proj, path, W = 1200, H = 600, wScale, wMax = 30;
  const motion = !matchMedia("(prefers-reduced-motion: reduce)").matches;

  function layoutMap() {
    W = Math.max(320, mapBox.clientWidth || 1200);
    proj = d3.geoEqualEarth().rotate([MAP_ROTATE, 0]).fitWidth(W, land);
    path = d3.geoPath(proj);
    const b = path.bounds(land);
    const pad = 8;
    proj.translate([proj.translate()[0], proj.translate()[1] - b[0][1] + pad]);
    H = Math.ceil(b[1][1] - b[0][1] + pad * 2);
    svg.attr("viewBox", `0 0 ${W} ${H}`);
    wMax = clamp(W / 40, 9, 30);
    gLand.selectAll("path").data(countries).join("path").attr("class", "country").attr("d", path)
      .on("pointerenter", (evt, f) => showCountryTip(evt, f))
      .on("pointermove", moveTip)
      .on("pointerleave", hideTip)
      .on("click", (evt, f) => {
        const units = (unitsByIso.get(f.properties.iso3) || []).sort((a, b) => b.v - a.v);
        if (units.length) selectOrigin(units[0].id === S.origin ? null : units[0].id);
      });
    usPathCache.clear();
  }
  const usPathCache = new Map();
  const usPath = (i) => {
    if (!usPathCache.has(i)) usPathCache.set(i, path(jurs[i]) || "");
    return usPathCache.get(i);
  };
  const width = (v) => Math.max(0.8, wScale(v));
  function setScale(arrows) {
    const top = S.scale === "year" ? d3.max(arrows, (a) => a.v) || 1 : MAXV;
    wScale = d3.scaleSqrt().domain([0, top]).range([0, wMax]);
  }

  function arrowGeom(p0, p1, w) {
    const dx = p1[0] - p0[0], dy = p1[1] - p0[1], L = Math.hypot(dx, dy);
    if (L < 4) return null;
    let nx = -dy / L, ny = dx / L;
    if (ny > 0) { nx = -nx; ny = -ny; } // bow every arc northward
    const bend = Math.min(0.2 * L, 140);
    const c = [(p0[0] + p1[0]) / 2 + nx * bend, (p0[1] + p1[1]) / 2 + ny * bend];
    const tx = p1[0] - c[0], ty = p1[1] - c[1], tl = Math.hypot(tx, ty) || 1;
    const hl = Math.min(Math.max(5.5, w * 1.15 + 4), tl * 0.6); // arrowhead length
    const hw = Math.max(3, w * 0.72 + 2); // arrowhead half-width
    const ux = tx / tl, uy = ty / tl;
    const e = [p1[0] - ux * hl * 0.8, p1[1] - uy * hl * 0.8];
    const base = [p1[0] - ux * hl, p1[1] - uy * hl];
    const head = `M${p1[0]},${p1[1]}L${base[0] - uy * hw},${base[1] + ux * hw}L${base[0] + uy * hw},${base[1] - ux * hw}Z`;
    return { d: `M${p0[0]},${p0[1]}Q${c[0]},${c[1]} ${e[0]},${e[1]}`, head };
  }

  let unitsByIso = new Map();
  function arrowsAt(y) {
    const i = y - Y0;
    const out = [];
    for (const id of flowIds) {
      const v = flowBy[id][i];
      if (!(v > 0)) continue;
      const o = originById[id];
      if (!o.at) continue;
      if (forcedBy[id]) {
        for (const p of forcedBy[id]) {
          const pv = p.a[i];
          if (pv > 0) {
            const L = D.forced.landings[p.land];
            out.push({ key: id + ">" + p.land, id, v: pv, from: o.at, to: L ? L.at : PORTS.east(y), dest: L ? L.name : COAST_NAME.east, forced: true });
          }
        }
      } else {
        const coast = o.to || "east";
        out.push({ key: id, id, v, from: o.at, to: (PORTS[coast] || PORTS.east)(y), dest: COAST_NAME[coast] });
      }
    }
    return out.sort((a, b) => a.v - b.v);
  }

  function drawMap() {
    const y = S.year;
    const F = flowsAt(y);
    const bi = basisInfo(F.basis);
    const approx = bi.cls !== "official";
    // country tint: origins with arrivals this year
    unitsByIso = new Map();
    for (const d of F.list) {
      for (const iso of originById[d.id].iso || []) {
        if (!unitsByIso.has(iso)) unitsByIso.set(iso, []);
        unitsByIso.get(iso).push(d);
      }
    }
    const landC = css("--land");
    const dark = d3.hsl(css("--bg")).l < 0.5;
    const topV = F.list.length ? F.list[0].v : 1;
    gLand.selectAll("path.country").attr("fill", (f) => {
      const u = unitsByIso.get(f.properties.iso3);
      if (!u) return landC;
      const top = u.reduce((a, b) => (b.v > a.v ? b : a));
      const sel = S.origin && u.some((d) => d.id === S.origin);
      // tint origins by region, stronger for larger flows
      const t = sel ? 0.55 : S.origin ? 0.06 : 0.06 + 0.3 * Math.sqrt(top.v / topV);
      return d3.interpolateRgb(landC, color[originById[top.id].group])(dark ? t * 0.75 : t);
    });
    // the United States as it stood on July 1
    const ids = (G.usYears[y] || []).filter((k) => jurs[k].properties.type !== "other");
    gUS.selectAll("path").data(ids, (k) => k).join("path").attr("class", "us-jur").attr("d", usPath);

    const raw = arrowsAt(y);
    setScale(raw);
    const byPort = d3.group(raw, (a) => a.to.join(","));
    const ends = new Map();
    for (const list of byPort.values()) {
      const p1 = proj(list[0].to);
      if (!p1) continue;
      const pts = list.map((a) => ({ a, p0: proj(a.from) })).filter((d) => d.p0);
      // perpendicular to the bundle's mean direction of approach
      let mx = 0, my = 0;
      for (const d of pts) { const L = Math.hypot(p1[0] - d.p0[0], p1[1] - d.p0[1]) || 1; mx += (p1[0] - d.p0[0]) / L; my += (p1[1] - d.p0[1]) / L; }
      const ml = Math.hypot(mx, my) || 1;
      const px = -my / ml, py = mx / ml;
      pts.sort((u, v) => (u.p0[0] * px + u.p0[1] * py) - (v.p0[0] * px + v.p0[1] * py));
      const sp = Math.min(3, 28 / Math.max(1, pts.length - 1));
      pts.forEach((d, k) => {
        const off = (k - (pts.length - 1) / 2) * sp;
        ends.set(d.a, [p1[0] + px * off, p1[1] + py * off]);
      });
    }
    const arrows = raw.map((a) => {
      const p0 = proj(a.from), p1 = ends.get(a);
      const w = width(a.v);
      const g = p0 && p1 ? arrowGeom(p0, p1, w) : null;
      return g ? Object.assign(a, g, { w, p0 }) : null;
    }).filter(Boolean);
    const dim = (a) => (S.origin && a.id !== S.origin ? 0.1 : null);
    gArrows.selectAll("path.arrow").data(arrows, (a) => a.key).join("path").attr("class", "arrow")
      .attr("d", (a) => a.d)
      .attr("stroke", (a) => color[originById[a.id].group])
      .attr("stroke-width", (a) => a.w)
      .attr("stroke-opacity", (a) => dim(a) ?? (S.origin ? 0.95 : a.w < 1.5 ? 0.42 : 0.66));
    gArrows.selectAll("path.head-tri").data(arrows, (a) => a.key).join("path").attr("class", "head-tri")
      .attr("d", (a) => a.head)
      .attr("fill", (a) => color[originById[a.id].group])
      .attr("fill-opacity", (a) => dim(a) ?? (S.origin ? 1 : 0.8));
    // moving dots along the larger arrows
    const flowing = motion ? arrows.filter((a) => a.w >= 2.2 && !dim(a)).slice(-36) : [];
    gFlow.selectAll("path").data(flowing, (a) => a.key).join("path").attr("class", "flow")
      .attr("d", (a) => a.d)
      .attr("stroke-width", (a) => Math.max(1.1, a.w * 0.34))
      .each(function (a) {
        const gap = clamp(a.w * 2.4, 10, 44);
        this.style.strokeDasharray = `0 ${gap}`;
        this.style.setProperty("--off", -gap + "px");
        this.style.setProperty("--dur", (gap / 26).toFixed(2) + "s");
      });
    // arrival points in use
    const ports = new Map();
    for (const a of arrows) ports.set(a.to.join(","), a.to);
    gPorts.selectAll("circle").data([...ports.values()], (p) => p.join(",")).join("circle").attr("class", "port")
      .attr("r", 2.6).attr("cx", (p) => proj(p)[0]).attr("cy", (p) => proj(p)[1]);
    // hover targets, widest on top
    gHit.selectAll("path").data(arrows, (a) => a.key).join("path").attr("class", "hit")
      .attr("d", (a) => a.d).attr("stroke-width", (a) => Math.max(12, a.w + 8))
      .on("pointerenter", (evt, a) => showArrowTip(evt, a, F, approx))
      .on("pointermove", moveTip)
      .on("pointerleave", hideTip)
      .on("click", (evt, a) => selectOrigin(S.origin === a.id ? null : a.id));
    drawLabels(arrows, F, approx);
    drawKey(y, arrows);
  }

  function drawLabels(arrows, F, approx) {
    // name the largest origins (one label per origin), skipping any that would collide
    const byOrigin = new Map();
    for (const a of arrows) {
      const o = originById[a.id];
      if (o.residual) continue;
      const cur = byOrigin.get(a.id);
      if (!cur || a.v > cur.v) byOrigin.set(a.id, { id: a.id, v: 0, p0: a.p0 });
    }
    for (const d of F.list) if (byOrigin.has(d.id)) byOrigin.get(d.id).v = d.v;
    // label the top three and anything above 1% of the year's arrivals
    let cands = [...byOrigin.values()].sort((a, b) => b.v - a.v).filter((c, k) => k < 3 || c.v >= 0.01 * (F.total || 0));
    if (S.origin) cands = cands.filter((c) => c.id === S.origin).concat(cands.filter((c) => c.id !== S.origin));
    const max = W < 640 ? 4 : 9;
    const placed = [];
    const out = [];
    for (const c of cands) {
      if (out.length >= max) break;
      const o = originById[c.id];
      const name = o.short || o.name;
      const val = fmtCount(c.v, approx);
      const wpx = Math.max(name.length * 6.6, val.length * 6) + 6;
      const x = c.p0[0], yTop = c.p0[1] - 30;
      const box = [x - wpx / 2, yTop, x + wpx / 2, c.p0[1] - 4];
      if (box[0] < 0 || box[2] > W || box[1] < 0) continue;
      if (placed.some((p) => !(box[2] < p[0] || box[0] > p[2] || box[3] < p[1] || box[1] > p[3]))) continue;
      placed.push(box);
      out.push({ id: c.id, x, y: c.p0[1], name, val });
    }
    const t = gLabels.selectAll("text").data(out, (d) => d.id).join((enter) => {
      const tx = enter.append("text").attr("class", "label").attr("text-anchor", "middle");
      tx.append("tspan").attr("class", "n");
      tx.append("tspan").attr("class", "v");
      return tx;
    });
    t.attr("x", (d) => d.x).attr("y", (d) => d.y - 18);
    t.select("tspan.n").attr("x", (d) => d.x).text((d) => d.name);
    t.select("tspan.v").attr("x", (d) => d.x).attr("dy", "1.15em").text((d) => d.val);
  }

  function drawKey(y, arrows) {
    const key = $("map-key");
    key.replaceChildren();
    const wk = el("span", "wkey");
    const top = wScale.domain()[1];
    const samples = [1e2, 1e3, 1e4, 1e5, 1e6].filter((v) => v <= top * 1.05 && v >= top / 2000).slice(-4);
    const ns = "http://www.w3.org/2000/svg";
    const s = document.createElementNS(ns, "svg");
    const maxw = width(samples[samples.length - 1] || top);
    const yLine = maxw / 2 + 1, yText = maxw + 14;
    let x = 0;
    for (const v of samples) {
      const w = width(v);
      const ln = document.createElementNS(ns, "line");
      ln.setAttribute("x1", x + w / 2); ln.setAttribute("x2", x + 34 - w / 2);
      ln.setAttribute("y1", yLine); ln.setAttribute("y2", yLine);
      ln.setAttribute("stroke", css("--ink-2"));
      ln.setAttribute("stroke-width", w);
      ln.setAttribute("stroke-linecap", "round");
      const tx = document.createElementNS(ns, "text");
      tx.setAttribute("x", x + 17); tx.setAttribute("y", yText); tx.setAttribute("text-anchor", "middle");
      tx.textContent = compact(v);
      s.append(ln, tx);
      x += 52;
    }
    s.setAttribute("width", Math.max(1, x - 18));
    s.setAttribute("height", yText + 3);
    s.setAttribute("aria-hidden", "true");
    wk.append(el("span", null, "Arrow width: people arriving"), s);
    key.append(wk);
    const seg = el("span", "seg seg-sm");
    seg.setAttribute("role", "group");
    seg.setAttribute("aria-label", "Arrow width scale");
    for (const [k, label] of [["all", "Same scale every year"], ["year", "Fit to " + y]]) {
      const b = el("button", null, label);
      b.type = "button";
      b.setAttribute("aria-pressed", String(S.scale === k));
      b.addEventListener("click", () => { S.scale = k; drawMap(); });
      seg.append(b);
    }
    key.append(seg);
    if (arrows.some((a) => a.forced)) key.append(el("span", "note", "Arrows from Africa this year carry enslaved people brought by force."));
    key.append(el("span", null, "Arrows end at a schematic point of arrival. Hover for numbers; click to follow one origin."));
  }

  function showArrowTip(evt, a, F, approx) {
    const o = originById[a.id];
    showTip(evt, (t) => {
      t.append(el("h4", null, o.name));
      tipRow(t, color[o.group], a.forced ? "Enslaved people landed" : "Arrived in " + S.year, fmtCount(a.v, approx || a.forced));
      if (F.total && !a.forced) t.append(el("div", "note", pct(a.v / F.total) + " of all arrivals"));
      t.append(el("div", "note", (a.forced ? "Landed: " : "Shown arriving at: ") + a.dest));
      if (o.note) t.append(el("div", "note", o.note));
    });
  }
  function showCountryTip(evt, f) {
    const iso = f.properties.iso3;
    showTip(evt, (t) => {
      t.append(el("h4", null, f.properties.name));
      if (iso === "USA") { t.append(el("div", "note", "Destination")); return; }
      const units = (unitsByIso.get(iso) || []).slice().sort((a, b) => b.v - a.v);
      if (!units.length) { t.append(el("div", "note", `No arrivals recorded from here in ${S.year}.`)); return; }
      const approx = basisInfo(D.flow.basis[S.year - Y0]).cls !== "official";
      for (const u of units) {
        const o = originById[u.id];
        tipRow(t, color[o.group], o.name, fmtCount(u.v, approx));
        if ((o.iso || []).length > 1) t.append(el("div", "note", `Reported as one unit spanning ${o.iso.length} present-day countries.`));
      }
    });
  }

  // ---------- timeline strip ----------
  const stripBox = $("strip");
  let strip = null;
  function layoutStrip() {
    const Wd = Math.max(320, stripBox.clientWidth || 1200);
    const Ht = Wd < 640 ? 96 : 120;
    const m = { t: 14, r: 2, b: 22, l: 2 };
    stripBox.replaceChildren();
    const s = d3.select(stripBox).append("svg").attr("viewBox", `0 0 ${Wd} ${Ht}`).attr("role", "img");
    const x = d3.scaleLinear().domain([Y0, Y1]).range([m.l, Wd - m.r]);
    strip = { s, Wd, Ht, m, x, gArea: s.append("g"), gAxis: s.append("g").attr("class", "axis"), gBand: s.append("g").attr("class", "band"), gEv: s.append("g") };
    strip.hover = s.append("line").attr("class", "hover-line").attr("y1", m.t).attr("y2", Ht - m.b).attr("visibility", "hidden");
    strip.cursor = s.append("line").attr("class", "cursor").attr("y1", m.t - 4).attr("y2", Ht - m.b);
    strip.knob = s.append("circle").attr("class", "cursor-knob").attr("r", 4).attr("cy", m.t - 4);
    const overlay = s.append("rect").attr("x", 0).attr("y", 0).attr("width", Wd).attr("height", Ht).attr("fill", "transparent");
    const yearAt = (evt) => clamp(Math.round(x.invert(d3.pointer(evt, s.node())[0])), Y0, Y1);
    let drag = false;
    overlay
      .on("pointerdown", (evt) => { drag = true; overlay.node().setPointerCapture(evt.pointerId); stopPlay(); setYear(yearAt(evt)); })
      .on("pointerup pointercancel", () => { drag = false; })
      .on("pointermove", (evt) => {
        const yy = yearAt(evt);
        if (drag) setYear(yy);
        strip.hover.attr("visibility", "visible").attr("x1", x(yy)).attr("x2", x(yy));
        showStripTip(evt, yy);
      })
      .on("pointerleave", () => { strip.hover.attr("visibility", "hidden"); hideTip(); });
    drawStrip();
  }
  function drawStrip() {
    if (!strip) return;
    const { s, Wd, Ht, m, x, gArea, gAxis, gBand, gEv } = strip;
    const data = S.series === "flow" ? flowGroups : stockGroups.filter((r) => r.year >= STOCK_FIRST);
    const series = d3.stack().keys(groups.map((g) => g.id)).offset(d3.stackOffsetExpand)(data);
    const y = d3.scaleLinear().domain([0, 1]).range([Ht - m.b, m.t]);
    const area = d3.area().curve(d3.curveMonotoneX).x((d) => x(d.data.year))
      .y0((d) => (isNaN(d[0]) ? y(0) : y(d[0]))).y1((d) => (isNaN(d[1]) ? y(0) : y(d[1])));
    gArea.selectAll("path").data(series, (d) => d.key).join("path").attr("d", area)
      .attr("fill", (d) => color[d.key]).attr("fill-opacity", 0.9);
    gAxis.selectAll("*").remove();
    const ticks = Wd < 640 ? [1607, 1700, 1800, 1900, 2024] : [1607, 1650, 1700, 1750, 1800, 1850, 1900, 1950, 2000, 2024];
    gAxis.selectAll("text").data(ticks).join("text").attr("x", (d) => x(d)).attr("y", Ht - 6)
      .attr("text-anchor", (d) => (d === Y0 ? "start" : d === Y1 ? "end" : "middle")).text((d) => d);
    if (S.series === "stock") {
      gAxis.append("text").attr("x", x((Y0 + STOCK_FIRST) / 2)).attr("y", (m.t + Ht - m.b) / 2 + 4).attr("text-anchor", "middle")
        .text(`Birthplace first recorded in the ${STOCK_FIRST} census`);
    }
    // where the record turns from estimates to official counts
    gBand.selectAll("*").remove();
    const firstOfficial = S.series === "flow" ? Y0 + D.flow.basis.search(/[HDAB]/) : SY[D.stock.kind.indexOf("acs")];
    const startX = S.series === "flow" ? x(Y0) : x(STOCK_FIRST);
    gBand.append("line").attr("x1", startX).attr("x2", x(firstOfficial)).attr("y1", 5).attr("y2", 5).attr("stroke", css("--muted")).attr("stroke-dasharray", "1 3");
    gBand.append("line").attr("x1", x(firstOfficial)).attr("x2", x(Y1)).attr("y1", 5).attr("y2", 5).attr("stroke", css("--muted"));
    if (Wd > 560) {
      gBand.append("text").attr("x", startX).attr("y", 2).text(S.series === "flow" ? "Estimates" : "Census every ten years");
      gBand.append("text").attr("x", x(firstOfficial) + 4).attr("y", 2).text(S.series === "flow" ? "Official counts" : "Yearly survey");
    }
    gEv.selectAll("*").remove();
    for (const e of D.events) {
      gEv.append("line").attr("class", "event-tick").attr("x1", x(e.y)).attr("x2", x(e.y)).attr("y1", Ht - m.b).attr("y2", Ht - m.b + 4);
    }
    s.attr("aria-label", (S.series === "flow" ? "Share of arrivals" : "Share of immigrants living in the US") + " by region of origin, " + Y0 + " to " + Y1);
    const leg = $("legend");
    leg.replaceChildren();
    for (const g of groups) {
      const sp = el("span");
      const b = el("b");
      b.style.background = color[g.id];
      sp.append(b, document.createTextNode(g.name));
      leg.append(sp);
    }
    moveCursor();
  }
  function moveCursor() {
    if (!strip) return;
    const cx = strip.x(S.year);
    strip.cursor.attr("x1", cx).attr("x2", cx);
    strip.knob.attr("cx", cx);
  }
  function showStripTip(evt, yy) {
    const row = S.series === "flow" ? flowGroups[yy - Y0] : stockGroups[yy - Y0];
    const ev = D.events.filter((e) => e.y === yy);
    showTip(evt, (t) => {
      t.append(el("h4", null, String(yy)));
      for (const e of ev) t.append(el("div", "note", e.title));
      const tot = d3.sum(groups, (g) => row[g.id]);
      if (!tot) { t.append(el("div", "note", S.series === "flow" ? "No arrivals recorded." : "Not recorded before " + STOCK_FIRST + ".")); return; }
      for (const g of [...groups].reverse()) if (row[g.id] > 0) tipRow(t, color[g.id], g.name, pct(row[g.id] / tot));
      t.append(el("div", "note", (S.series === "flow" ? "Arrivals: " : "Born abroad: ") + fmtInt(Math.round(tot))));
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
      const present = new Map(F.list.map((d) => [d.id, d.v]));
      rows = origins.filter((o) => o.name.toLowerCase().includes(q)).map((o) => ({ id: o.id, v: present.get(o.id) || 0 })).sort((a, b) => b.v - a.v);
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
      const vl = el("span", "vl", d.v ? fmtCount(d.v, approx) : "–");
      if (d.v && F.total) vl.append(el("small", null, pct(d.v / F.total)));
      const bar = el("span", "bar");
      const i = el("i");
      i.style.width = (100 * d.v) / max + "%";
      i.style.background = color[o.group];
      bar.append(i);
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
    const arr = flowBy[o.id] || new Float64Array(NY);
    let peak = 0, peakY = null, total = 0;
    arr.forEach((v, i) => { total += v; if (v > peak) { peak = v; peakY = Y0 + i; } });
    const nat = interp(D.stock.nat.o[o.id], S.year);
    let txt = peakY ? `Most arrivals in one year: ${fmtInt(Math.round(peak))} in ${peakY}. ${fmtInt(Math.round(total))} in all since ${Y0}.` : "No arrivals recorded.";
    if (nat) txt += ` ${nat.exact ? "" : "About "}${fmtInt(Math.round(nat.v))} people born here lived in the US in ${S.year}.`;
    if (o.note) txt += " " + o.note;
    box.append(el("p", null, txt));
    const Wd = Math.max(260, box.clientWidth - 28), Ht = 64;
    const x = d3.scaleLinear().domain([Y0, Y1]).range([0, Wd]);
    const yS = d3.scaleLinear().domain([0, peak || 1]).range([Ht - 2, 4]);
    const s = d3.create("svg").attr("viewBox", `0 0 ${Wd} ${Ht}`).attr("aria-label", `Arrivals from ${o.name} by year`);
    const pts = Array.from(arr, (v, i) => [Y0 + i, v]);
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
    const F = flowsAt(y);
    const bi = basisInfo(F.basis);
    const est = bi.cls === "estimate";
    const lede = $("lede");
    lede.replaceChildren();
    const txt = (t) => lede.append(document.createTextNode(t));
    const strong = (t) => lede.append(el("strong", null, t));
    if (F.total) {
      const n = est ? roundEst(F.total) : F.total;
      txt(est ? "About " : "");
      strong(fmtInt(n));
      txt(` ${n === 1 ? "person" : "people"} arrived in ${y}. `);
      const named = F.list.filter((d) => !originById[d.id].residual).slice(0, 2);
      if (named.length) {
        txt(named[1] ? "The largest groups came from " : "The largest group came from ");
        strong(originById[named[0].id].name);
        txt(` (${pct(named[0].v / F.total)})`);
        if (named[1]) { txt(" and "); strong(originById[named[1].id].name); txt(` (${pct(named[1].v / F.total)})`); }
        txt(". ");
      }
      const forced = F.list.filter((d) => originById[d.id].forced).reduce((s, d) => s + d.v, 0);
      if (forced > 0) txt(`About ${fmtInt(roundEst(forced))} were enslaved Africans brought by force. `);
    } else {
      txt(y === Y1 ? `Arrivals for ${y} haven't been published yet. ` : `No arrivals are recorded for ${y}. `);
    }
    const nt = interp(D.stock.nat.total, y), np = interp(D.stock.nat.pop, y);
    if (nt && np) { txt(nt.exact ? "" : "About "); strong(pct(nt.v / np.v)); txt(" of US residents were born abroad."); }
    const b = $("basis");
    b.className = "basis " + bi.cls;
    b.replaceChildren(el("i"), document.createTextNode(bi.label));
    b.title = bi.long || "";
    const ev = currentEvent(y, 12);
    const ctx = $("context");
    ctx.replaceChildren();
    if (ev) ctx.append(el("b", null, `${ev.y} · ${ev.title}. `), document.createTextNode(ev.t));
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
  $("play").addEventListener("click", () => (S.playing ? stopPlay() : startPlay()));
  $("slider").addEventListener("input", (e) => { stopPlay(); setYear(+e.target.value); });
  $("slider").addEventListener("focus", () => stripBox.classList.add("slider-focus"));
  $("slider").addEventListener("blur", () => stripBox.classList.remove("slider-focus"));
  $("q").addEventListener("input", (e) => { S.query = e.target.value; drawList(); });
  $("more").addEventListener("click", () => { S.showAll = !S.showAll; if (!S.showAll) S.query = ""; $("q").value = S.query; drawList(); });
  $("series").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    S.series = b.dataset.series;
    for (const x of $("series").querySelectorAll("button")) x.setAttribute("aria-pressed", String(x === b));
    drawStrip();
  });
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, select") && e.target.id !== "slider") return;
    if (e.target.id === "slider") return; // the range input handles its own arrows
    if (e.key === "ArrowRight") { stopPlay(); setYear(S.year + (e.shiftKey ? 10 : 1)); e.preventDefault(); }
    else if (e.key === "ArrowLeft") { stopPlay(); setYear(S.year - (e.shiftKey ? 10 : 1)); e.preventDefault(); }
    else if (e.key === " " && !e.target.closest("button, summary, a")) { S.playing ? stopPlay() : startPlay(); e.preventDefault(); }
    else if (e.key === "Escape" && S.origin) selectOrigin(null);
  });

  const onTheme = () => { readColors(); drawStrip(); drawAll(); };
  try { matchMedia("(prefers-color-scheme: dark)").addEventListener("change", onTheme); } catch (e) { /* old browsers */ }
  new MutationObserver(onTheme).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  let rT = null, lastW = document.documentElement.clientWidth;
  window.addEventListener("resize", () => {
    clearTimeout(rT);
    rT = setTimeout(() => {
      if (Math.abs(document.documentElement.clientWidth - lastW) < 4) return;
      lastW = document.documentElement.clientWidth;
      layoutMap(); layoutStrip(); drawAll();
    }, 150);
  });

  // ---------- boot ----------
  $("y-start").textContent = Y0;
  $("y-end").textContent = Y1;
  const sl = $("slider");
  sl.min = Y0; sl.max = Y1; sl.value = S.year;
  layoutMap();
  layoutStrip();
  drawAbout();
  drawAll();
})();
