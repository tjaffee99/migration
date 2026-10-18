/* Atlas of Arrivals — client app. Reads window.__DATA__ (built by scripts/build/build_data.py)
   and window.__GEO__ (built by scripts/build/build_site.py). No network access at runtime. */
(function () {
  "use strict";
  const D = window.__DATA__;
  const G = window.__GEO__;
  const Y0 = D.start, Y1 = D.end, NY = Y1 - Y0 + 1;
  const STOCK_FIRST = D.stock.years[0];

  // ---------- helpers ----------
  const $ = (id) => document.getElementById(id);
  const fmtInt = d3.format(",");
  const compactFmt = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
  const compact = (n) => (n == null ? "—" : n < 1000 ? String(Math.round(n)) : compactFmt.format(n));
  const pct = (x, d = 1) => (x == null ? "—" : (x * 100).toFixed(x < 0.1 && d ? d : x < 0.995 ? d : 0) + "%");
  const roundEst = (n) => {
    if (n < 100) return Math.round(n);
    if (n < 1000) return Math.round(n / 10) * 10;
    if (n < 100000) return Math.round(n / 100) * 100;
    return Math.round(n / 1000) * 1000;
  };
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
  let groupColor = {};
  function readColors() {
    groupColor = Object.fromEntries(groups.map((g) => [g.id, css("--s" + g.slot)]));
  }
  readColors();

  // flows: expand sparse [startIdx, values] into Float64Array per origin
  const flowByOrigin = {};
  for (const [id, [s, vals]] of Object.entries(D.flow.o)) {
    const a = new Float64Array(NY);
    for (let i = 0; i < vals.length; i++) a[s + i] = vals[i] || 0;
    flowByOrigin[id] = a;
  }
  const flowIds = Object.keys(flowByOrigin);
  const flowGroupSeries = []; // per year {year, g1:.., g2:..}
  for (let i = 0; i < NY; i++) {
    const row = { year: Y0 + i };
    for (const g of groups) row[g.id] = 0;
    for (const id of flowIds) {
      const v = flowByOrigin[id][i];
      if (v) row[originById[id].group] += v;
    }
    flowGroupSeries.push(row);
  }

  // stock interpolation
  const SY = D.stock.years;
  function interp(vals, y) {
    if (!vals) return null;
    if (y < SY[0] || y > SY[SY.length - 1]) return null;
    const i = d3.bisectRight(SY, y) - 1;
    if (SY[i] === y) return vals[i] == null ? null : { v: vals[i], exact: true, a: y, b: y };
    const a = vals[i], b = vals[i + 1];
    if (a == null || b == null) return null;
    const t = (y - SY[i]) / (SY[i + 1] - SY[i]);
    return { v: a + (b - a) * t, exact: false, a: SY[i], b: SY[i + 1] };
  }
  const stockKindAt = (y) => {
    if (y < SY[0]) return null;
    const i = SY.indexOf(y);
    if (i >= 0) return D.stock.kind[i];
    const j = d3.bisectRight(SY, y) - 1;
    return { a: SY[j], b: SY[j + 1] };
  };
  // national stock by group, every year from first benchmark
  const stockGroupSeries = [];
  {
    const natG = D.stock.nat.g; // {groupId: [per benchmark]}
    for (let y = Y0; y <= Y1; y++) {
      const row = { year: y };
      for (const g of groups) {
        const r = y >= STOCK_FIRST ? interp(natG[g.id], y) : null;
        row[g.id] = r ? r.v : 0;
      }
      stockGroupSeries.push(row);
    }
  }

  // ---------- state ----------
  const params = (() => {
    const h = (location.hash || "").replace("#", "");
    const y = parseInt(h, 10);
    return { year: y >= Y0 && y <= Y1 ? y : D.defaultYear || 1910 };
  })();
  const S = {
    year: params.year,
    mapMode: "share",
    origin: null,
    compSeries: "flow",
    compScale: "share",
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
    const pad = 14;
    const r = tip.getBoundingClientRect();
    let x = evt.clientX + pad, y = evt.clientY + pad;
    if (x + r.width > window.innerWidth - 8) x = evt.clientX - r.width - pad;
    if (y + r.height > window.innerHeight - 8) y = evt.clientY - r.height - pad;
    tip.style.left = clamp(x, 8, window.innerWidth - r.width - 8) + "px";
    tip.style.top = clamp(y, 8, window.innerHeight - r.height - 8) + "px";
  }
  const hideTip = () => { tip.hidden = true; };
  function tipRow(parent, color, label, value) {
    const row = el("div", "row");
    const i = el("i");
    i.style.background = color || "transparent";
    row.append(i, el("span", null, label), el("b", null, value));
    parent.append(row);
  }

  // ---------- flows for a year ----------
  function flowsAt(y) {
    const i = y - Y0;
    const list = [];
    for (const id of flowIds) {
      const v = flowByOrigin[id][i];
      if (v > 0) list.push({ id, v });
    }
    list.sort((a, b) => b.v - a.v);
    const total = D.flow.total[i];
    return { list, total, basis: D.flow.basis[i] };
  }
  const basisInfo = (code) => D.basisInfo[code] || { label: "—", cls: "" };

  // ---------- US map ----------
  const usFeatures = topojson.feature(G.us, G.us.objects.jurisdictions).features;
  const nationGeo = topojson.mesh(G.nation, G.nation.objects.nation);
  const nationFeat = topojson.feature(G.nation, G.nation.objects.nation);
  const activeIdx = G.usYears; // {year: [feature indices]}
  const usBox = $("usmap");
  const usSvg = d3.select(usBox).append("svg").attr("role", "img").attr("aria-label", "Map of the United States");
  const gBase = usSvg.append("g");
  const gJur = usSvg.append("g");
  const gLab = usSvg.append("g");
  const gLand = usSvg.append("g");
  let usProj, usPath, usW = 960, usH = 600;
  const featCache = new Map(); // index -> {d, c, a}

  function layoutUS() {
    usW = Math.max(320, usBox.clientWidth || 960);
    usH = Math.round(usW * 0.62);
    usSvg.attr("viewBox", `0 0 ${usW} ${usH}`);
    usProj = d3.geoAlbersUsa().fitExtent([[6, 6], [usW - 6, usH - 6]], nationFeat);
    usPath = d3.geoPath(usProj);
    featCache.clear();
    gBase.selectAll("path").data([nationFeat]).join("path").attr("class", "nation-out").attr("d", usPath);
  }
  function feat(i) {
    let c = featCache.get(i);
    if (!c) {
      const f = usFeatures[i];
      const d = usPath(f) || "";
      c = { d, c: d ? usPath.centroid(f) : [NaN, NaN], a: d ? usPath.area(f) : 0 };
      featCache.set(i, c);
    }
    return c;
  }

  // per-jurisdiction metrics at year
  function jurData(f, y) {
    const key = f.properties.key;
    const out = { key };
    if (!key) return out;
    if (y >= STOCK_FIRST) {
      const st = D.stock.st[key];
      if (st) {
        const pop = interp(st.pop, y), fb = interp(st.fb, y);
        out.pop = pop && pop.v;
        out.fb = fb && fb.v;
        out.fbExact = fb && fb.exact;
        out.span = fb && [fb.a, fb.b];
        if (st.o) out.st = st;
      }
    }
    if (out.pop == null) {
      const p = D.colonial.pop[key];
      if (p) {
        const r = interpYears(p.y, p.v, y);
        if (r) { out.pop = r.v; out.popEst = !r.exact; out.popSpan = [r.a, r.b]; }
      }
    }
    return out;
  }
  function interpYears(ys, vs, y) {
    if (y < ys[0] || y > ys[ys.length - 1]) return null;
    const i = d3.bisectRight(ys, y) - 1;
    if (ys[i] === y) return { v: vs[i], exact: true, a: y, b: y };
    const t = (y - ys[i]) / (ys[i + 1] - ys[i]);
    return { v: vs[i] + (vs[i + 1] - vs[i]) * t, exact: false, a: ys[i], b: ys[i + 1] };
  }
  // State birthplace mix at year y. Census tables exist only for some years; between two of them
  // (at most maxGap years apart) the mix is interpolated and scaled to the state's foreign-born total.
  const PARTIAL = new Set(D.stock.partialYears || []);
  const MAXGAP = D.stock.maxGap || 30;
  function stateOrigins(st, y) {
    if (!st || !st.o || !st.oy || !st.oy.length) return null;
    const ys = st.oy.map((k) => SY[k]);
    let lo = -1, hi = -1;
    for (let n = 0; n < ys.length; n++) {
      if (ys[n] <= y) lo = n;
      if (ys[n] >= y && hi < 0) hi = n;
    }
    if (lo < 0 || hi < 0) return null;
    const ka = st.oy[lo], kb = st.oy[hi];
    const m = new Map();
    if (ys[lo] === y) {
      for (const [id, arr] of Object.entries(st.o)) if (arr[ka] != null) m.set(id, arr[ka]);
      return { m, exact: true, a: y, b: y, partial: PARTIAL.has(y) };
    }
    if (ys[hi] - ys[lo] > MAXGAP) return null;
    let sa = 0, sb = 0;
    for (const arr of Object.values(st.o)) { sa += arr[ka] || 0; sb += arr[kb] || 0; }
    if (!sa || !sb) return null;
    const t = (y - ys[lo]) / (ys[hi] - ys[lo]);
    const fb = interp(st.fb, y);
    const scale = fb ? fb.v : sa + (sb - sa) * t;
    for (const [id, arr] of Object.entries(st.o)) {
      const a = arr[ka], b = arr[kb];
      if (a == null || b == null) continue;
      m.set(id, (a / sa + (b / sb - a / sa) * t) * scale);
    }
    return { m, exact: false, a: ys[lo], b: ys[hi], partial: PARTIAL.has(ys[lo]) || PARTIAL.has(ys[hi]) };
  }
  function topOrigins(st, y, n) {
    const so = stateOrigins(st, y);
    if (!so) return null;
    const list = [];
    for (const [id, v] of so.m) if (v > 0) list.push({ id, v });
    if (!list.length) return null;
    list.sort((a, b) => b.v - a.v);
    return n ? list.slice(0, n) : list;
  }

  const SHARE_BREAKS = [0.02, 0.05, 0.1, 0.15, 0.2, 0.3];
  const POP_BREAKS = [10e3, 50e3, 250e3, 1e6, 3e6, 10e6];
  let originBreaks = null;
  function originBreaksFor(id) {
    let max = 0;
    for (const st of Object.values(D.stock.st)) {
      const arr = st.o && st.o[id];
      if (arr) for (const v of arr) if (v > max) max = v;
    }
    const nice = [100, 500, 1e3, 2.5e3, 5e3, 1e4, 2.5e4, 5e4, 1e5, 2.5e5, 5e5, 1e6, 2.5e6, 5e6];
    const b = nice.filter((x) => x < max);
    return b.slice(-6);
  }
  const seqColor = (breaks, prefix) => (v) => {
    if (v == null) return null;
    let k = 0;
    while (k < breaks.length && v >= breaks[k]) k++;
    // with fewer than 6 breaks, spread over the ramp's upper end so contrast stays high
    const off = 6 - breaks.length;
    return css("--" + prefix + (k + off > 6 ? 6 : k === 0 ? 0 : k + off));
  };
  function luminance(c) {
    const rgb = d3.rgb(c);
    const f = (x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(rgb.r) + 0.7152 * f(rgb.g) + 0.0722 * f(rgb.b);
  }

  function effectiveMapMode(y) {
    if (S.mapMode === "share" && y < STOCK_FIRST) return "pop";
    return S.mapMode;
  }

  function drawUS() {
    const y = S.year;
    const ids = activeIdx[y] || [];
    const mode = effectiveMapMode(y);
    const land = css("--land"), nodata = css("--nodata"), landOut = css("--land-out");
    const ink = css("--ink"), panel = css("--panel");
    const shareC = seqColor(SHARE_BREAKS, "q");
    const popC = seqColor(POP_BREAKS, "q");
    const oC = originBreaks ? seqColor(originBreaks, "q") : null;
    let anyOriginData = false;
    let anyUnlisted = false;

    const PRI = { other: 0, foreign: 0, unorganized: 1, territory: 2, district: 3, colony: 3, state: 3 };
    const ordered = ids.slice().sort((a, b) => (PRI[usFeatures[a].properties.type] ?? 3) - (PRI[usFeatures[b].properties.type] ?? 3) || feat(b).a - feat(a).a);
    const rows = ordered.map((i) => {
      const f = usFeatures[i];
      const jd = jurData(f, y);
      let fill = nodata, label = null;
      const t = f.properties.type;
      if (t === "other" || t === "foreign") {
        fill = landOut;
      } else if (mode === "share") {
        if (jd.fb != null && jd.pop) {
          fill = shareC(jd.fb / jd.pop);
          const named = (topOrigins(jd.st, y) || []).filter((d) => !originById[d.id].residual);
          label = named.length ? originById[named[0].id].short || originById[named[0].id].name : jd.fb / jd.pop < 0.005 ? "<1%" : pct(jd.fb / jd.pop, 0);
        }
      } else if (mode === "pop") {
        if (jd.pop != null) { fill = popC(jd.pop); label = compact(jd.pop); }
      } else if (mode === "origin" && S.origin) {
        const so = stateOrigins(jd.st, y);
        if (so) {
          anyOriginData = true;
          const v = so.m.get(S.origin);
          if (v == null) {
            fill = so.partial ? nodata : land;
            if (so.partial) anyUnlisted = true;
          } else {
            fill = v > 0 ? oC(v) : land;
            if (v >= 1) label = compact(v);
          }
        }
      }
      return { i, f, jd, fill, label };
    });

    gJur.selectAll("path.jur")
      .data(rows, (r) => r.i)
      .join("path")
      .attr("class", "jur")
      .attr("fill-opacity", (r) => (r.f.properties.type === "territory" || r.f.properties.type === "unorganized" ? 0.92 : 1))
      .attr("d", (r) => feat(r.i).d)
      .attr("fill", (r) => r.fill)
      .on("pointerenter", function (evt, r) { d3.select(this).raise(); showJurTip(evt, r); })
      .on("pointermove", moveTip)
      .on("pointerleave", hideTip)
      .on("click", (evt, r) => { showJurTip(evt, r); })
      .order();

    // label a shape only when the text plausibly fits inside it
    const labRows = rows.filter((r) => {
      const fc = feat(r.i);
      if (!r.label || !isFinite(fc.c[0])) return false;
      const w = r.label.length * 6.1 + 6;
      return fc.a > (usW < 600 ? 1400 : 1100) && w * 14 < fc.a * 0.55 && w < Math.sqrt(fc.a) * 1.9;
    });
    gLab.selectAll("text")
      .data(labRows, (r) => r.i)
      .join("text")
      .attr("class", "maplabel")
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .attr("x", (r) => feat(r.i).c[0])
      .attr("y", (r) => feat(r.i).c[1])
      .attr("fill", (r) => (luminance(r.fill) < 0.28 ? "#ffffff" : "#0f1720"))
      .attr("stroke", (r) => (luminance(r.fill) < 0.28 ? "rgba(0,0,0,0.25)" : "rgba(255,255,255,0.55)"))
      .text((r) => r.label);

    // slave-trade landings (forced migration), shown where landing region is recorded
    const lands = [];
    const i = y - Y0;
    for (const [k, L] of Object.entries(D.colonial.landings)) {
      const [s, vals] = L.v;
      const v = i >= s && i < s + vals.length ? vals[i - s] : 0;
      if (v > 0) {
        const p = usProj([L.lon, L.lat]);
        if (p) lands.push({ k, L, v, x: p[0], y: p[1] });
      }
    }
    const rScale = d3.scaleSqrt().domain([0, D.colonial.landingMax]).range([0, usW < 600 ? 18 : 28]);
    gLand.selectAll("circle")
      .data(lands, (d) => d.k)
      .join("circle")
      .attr("class", "landing")
      .attr("cx", (d) => d.x).attr("cy", (d) => d.y)
      .attr("r", (d) => Math.max(4, rScale(d.v)))
      .on("pointerenter", (evt, d) => showTip(evt, (t) => {
        t.append(el("h4", null, d.L.name));
        tipRow(t, css("--s4"), "Enslaved Africans landed", "≈" + fmtInt(Math.round(d.v)));
        t.append(el("div", "note", D.colonial.landingNote));
      }))
      .on("pointermove", moveTip)
      .on("pointerleave", hideTip);

    // legend + note
    const leg = $("us-legend");
    leg.replaceChildren();
    const note = $("map-note");
    note.replaceChildren();
    const addRamp = (breaks, fmt, prefix) => {
      const ramp = el("span", "ramp");
      const off = 6 - breaks.length;
      const steps = [0].concat(breaks.map((_, k) => k + 1 + off));
      steps.forEach((s, k) => {
        const sp = el("span");
        const b = el("b");
        b.style.background = css("--" + prefix + Math.min(6, s));
        sp.append(b, el("span", null, k === 0 ? "<" + fmt(breaks[0]) : fmt(breaks[k - 1]) + "+"));
        ramp.append(sp);
      });
      leg.append(ramp);
    };
    const sw = (color, text, dot) => {
      const s = el("span", "sw");
      const b = el("b", dot ? "dot" : null);
      b.style.background = color;
      s.append(b, el("span", null, text));
      leg.append(s);
    };
    let title = "Where immigrants lived";
    if (mode === "share") {
      addRamp(SHARE_BREAKS, (v) => Math.round(v * 100) + "%", "q");
      sw(nodata, "No data");
      note.append(el("span", null, "Share of each state's residents born outside the US. Labels name the largest birthplace where the state breakdown exists."));
    } else if (mode === "pop") {
      title = "Population";
      addRamp(POP_BREAKS, compact, "q");
      sw(nodata, "No estimate");
      if (S.mapMode === "share" && y < STOCK_FIRST) {
        note.append(el("span", null, `The census first recorded birthplace in ${STOCK_FIRST}. Before that, the map shows each colony's or state's population.`));
      } else {
        note.append(el("span", null, "Total population of each state, territory or colony."));
      }
    } else if (mode === "origin") {
      const o = originById[S.origin];
      title = o ? "Born in " + o.name : "Born in…";
      if (oC) addRamp(originBreaks, compact, "q");
      sw(land, "None recorded");
      sw(nodata, anyUnlisted ? "Not listed separately or no data" : "No state breakdown");
      if (!anyOriginData) {
        const near = nearestStateOriginYear(y);
        note.append(el("span", null, `State-by-birthplace counts aren't available for ${y}.` + (near ? ` Nearest year with them: ${near}.` : "")));
      } else {
        const so = stateOrigins(D.stock.st["36"] || Object.values(D.stock.st).find((x) => x.oy), y);
        let txt = "Residents born in this origin, by state.";
        if (so && !so.exact) txt += ` State birthplace mix interpolated between the ${so.a} and ${so.b} counts.`;
        if (anyUnlisted) txt += " Early censuses listed only each state's main birthplaces.";
        note.append(el("span", null, txt));
      }
    }
    if (lands.length) sw(css("--s4"), "Enslaved Africans landed this year", true);
    sw(landOut, "Outside colonial or US jurisdiction");
    $("map-title").textContent = title;

    // basis pill for map
    const kind = y >= STOCK_FIRST && mode !== "pop" ? stockKindAt(y) : null;
    if (kind) {
      const p = el("span", "pill " + (typeof kind === "string" ? "official" : "interp"));
      p.append(el("i"), el("span", null, typeof kind === "string" ? (kind === "acs" ? "Survey estimate (ACS)" : "Census count") : `Interpolated ${kind.a}–${kind.b}`));
      note.prepend(p);
    }
  }
  const stateOriginYears = (() => {
    const ys = new Set();
    for (const st of Object.values(D.stock.st)) for (const k of st.oy || []) ys.add(SY[k]);
    return [...ys].sort((a, b) => a - b);
  })();
  function nearestStateOriginYear(y) {
    if (!stateOriginYears.length) return null;
    return stateOriginYears.reduce((best, s) => (Math.abs(s - y) < Math.abs(best - y) ? s : best), stateOriginYears[0]);
  }

  function showJurTip(evt, r) {
    const y = S.year;
    const p = r.f.properties;
    showTip(evt, (t) => {
      t.append(el("h4", null, p.name));
      const typeLabel = { colony: "Colony", state: "State", territory: "Territory", district: "District", unorganized: "Unorganized territory", other: "Not part of the US or its colonies at this date", foreign: "Not yet part of the US" }[p.type] || p.type;
      t.append(el("div", "note", typeLabel + (p.owner ? " · " + p.owner : "")));
      const jd = r.jd;
      if (jd.pop != null) tipRow(t, null, jd.popEst ? "Population (interpolated)" : "Population", (jd.popEst || (y >= STOCK_FIRST && !jd.fbExact) ? "≈" : "") + fmtInt(Math.round(jd.pop)));
      if (jd.fb != null) {
        tipRow(t, null, "Born abroad", (jd.fbExact ? "" : "≈") + fmtInt(Math.round(jd.fb)) + (jd.pop ? " (" + pct(jd.fb / jd.pop) + ")" : ""));
      }
      const so = stateOrigins(jd.st, y);
      const top = topOrigins(jd.st, y, 6);
      if (top) {
        const tot = jd.fb || d3.sum(topOrigins(jd.st, y), (d) => d.v);
        for (const d of top) {
          const o = originById[d.id];
          tipRow(t, groupColor[o.group], o.name, compact(d.v) + (tot ? " · " + pct(d.v / tot, 0) : ""));
        }
      } else if (y >= STOCK_FIRST && jd.fb != null) {
        t.append(el("div", "note", "Birthplace breakdown not available for this year."));
      }
      if (S.mapMode === "origin" && S.origin && so) {
        const v = so.m.get(S.origin);
        tipRow(t, groupColor[originById[S.origin].group], "Born in " + originById[S.origin].name, v == null ? "not listed" : (so.exact ? "" : "≈") + fmtInt(Math.round(v)));
      }
      if (so && !so.exact) t.append(el("div", "note", `Birthplace mix interpolated between the ${so.a} and ${so.b} counts.`));
      if (so && so.partial) t.append(el("div", "note", "The census listed only each state's main birthplaces; the rest are under other or not specified."));
      if (so && (so.a === 1950 || so.b === 1950)) t.append(el("div", "note", "The 1950 state counts cover white foreign-born residents only."));
      if (jd.span && jd.span[0] !== jd.span[1]) t.append(el("div", "note", `Interpolated between the ${jd.span[0]} and ${jd.span[1]} counts.`));
      if (p.note) t.append(el("div", "note", p.note));
    });
  }

  // ---------- Ledger ----------
  function drawLedger() {
    const y = S.year;
    const F = flowsAt(y);
    const bi = basisInfo(F.basis);
    $("ledger-year").textContent = y;
    const pill = $("flow-basis");
    pill.className = "pill " + bi.cls;
    pill.lastChild.textContent = bi.label;
    pill.title = bi.long || "";
    const est = bi.cls === "estimate"; // the total itself is an estimate
    const split = bi.cls !== "official"; // per-origin values are estimated splits
    $("flow-total").textContent = F.total == null ? "—" : (est ? "≈" : "") + fmtInt(est ? roundEst(F.total) : F.total);
    $("flow-unit").textContent = F.total === 1 ? "person arrived" : "people arrived";

    // composition bar
    const gsum = flowGroupSeries[y - Y0];
    const tot = d3.sum(groups, (g) => gsum[g.id]) || 1;
    const bar = $("compbar");
    bar.replaceChildren();
    const gl = $("groups");
    gl.replaceChildren();
    for (const g of groups) {
      const v = gsum[g.id];
      if (v > 0) {
        const s = el("span");
        s.style.flex = String(v / tot);
        s.style.background = groupColor[g.id];
        bar.append(s);
      }
      const row = el("div");
      const b = el("b");
      b.style.background = groupColor[g.id];
      row.append(b, el("span", "gname", g.short || g.name), el("span", "gval", v > 0 ? (v / tot < 0.005 ? "<1%" : pct(v / tot, 0)) : "–"));
      row.title = g.name;
      row.style.opacity = v > 0 ? 1 : 0.45;
      gl.append(row);
    }

    // origin list
    const list = $("olist");
    list.replaceChildren();
    const q = S.query.trim().toLowerCase();
    let rows = F.list;
    if (q) {
      const present = new Map(F.list.map((d) => [d.id, d.v]));
      rows = origins
        .filter((o) => o.name.toLowerCase().includes(q) || (o.alt || "").toLowerCase().includes(q))
        .map((o) => ({ id: o.id, v: present.get(o.id) || 0 }))
        .sort((a, b) => b.v - a.v);
    }
    const max = F.list.length ? F.list[0].v : 1;
    const shown = q || S.showAll ? rows : rows.slice(0, 12);
    if (!shown.length) {
      list.append(el("p", "empty", q ? "No origin matches that search." : "No recorded arrivals this year."));
    }
    for (const d of shown) {
      const o = originById[d.id];
      const b = el("button", "orow");
      b.type = "button";
      b.setAttribute("role", "listitem");
      b.setAttribute("aria-pressed", String(S.origin === d.id));
      const key = el("span", "key");
      key.style.background = groupColor[o.group];
      const vl = el("span", "vl");
      vl.append(document.createTextNode(d.v ? (split ? "≈" : "") + fmtInt(split ? roundEst(d.v) : Math.round(d.v)) : "–"));
      if (d.v && F.total) vl.append(el("small", null, pct(d.v / F.total, d.v / F.total < 0.01 ? 1 : 0)));
      const barEl = el("span", "bar");
      const bi2 = el("i");
      bi2.style.width = (100 * d.v) / max + "%";
      bi2.style.background = groupColor[o.group];
      barEl.append(bi2);
      b.append(key, el("span", "nm", o.name), vl, barEl);
      b.addEventListener("click", () => selectOrigin(S.origin === d.id ? null : d.id));
      list.append(b);
    }
    const more = $("more");
    more.hidden = !!q || F.list.length <= 12;
    more.textContent = S.showAll ? "Show top 12" : `Show all ${F.list.length} origins`;
    drawDetail();
  }

  function drawDetail() {
    const box = $("detail");
    if (!S.origin) { box.hidden = true; return; }
    const o = originById[S.origin];
    box.hidden = false;
    box.replaceChildren();
    const h = el("h3");
    const key = el("span", "key");
    key.style.cssText = `width:14px;height:4px;border-radius:2px;background:${groupColor[o.group]}`;
    h.append(key, document.createTextNode(o.name));
    box.append(h);
    box.append(el("div", "meta", groupById[o.group].name + (o.note ? " · " + o.note : "")));
    const arr = flowByOrigin[o.id];
    if (arr) {
      let peak = 0, peakY = null, total = 0;
      arr.forEach((v, i) => { total += v; if (v > peak) { peak = v; peakY = Y0 + i; } });
      box.append(el("div", "meta", peakY ? `Peak year: ${peakY} (${fmtInt(Math.round(peak))} arrivals). Total recorded or estimated, ${Y0}–${Y1}: ${fmtInt(Math.round(total))}.` : "No arrivals recorded."));
      const W = Math.max(240, box.clientWidth || 320), H = 72;
      const x = d3.scaleLinear().domain([Y0, Y1]).range([2, W - 2]);
      const yS = d3.scaleLinear().domain([0, peak || 1]).range([H - 14, 4]);
      const svg = d3.create("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img").attr("aria-label", `Arrivals from ${o.name} by year`);
      const pts = Array.from(arr, (v, i) => [Y0 + i, v]);
      svg.append("path").attr("d", d3.area().x((d) => x(d[0])).y0(H - 14).y1((d) => yS(d[1]))(pts)).attr("fill", groupColor[o.group]).attr("fill-opacity", 0.12);
      svg.append("path").attr("d", d3.line().x((d) => x(d[0])).y((d) => yS(d[1]))(pts)).attr("fill", "none").attr("stroke", groupColor[o.group]).attr("stroke-width", 1.5);
      svg.append("line").attr("x1", 0).attr("x2", W).attr("y1", H - 14).attr("y2", H - 14).attr("stroke", css("--line-strong"));
      svg.append("line").attr("x1", x(S.year)).attr("x2", x(S.year)).attr("y1", 2).attr("y2", H - 14).attr("stroke", css("--ink")).attr("stroke-width", 1.2);
      for (const t of [1607, 1700, 1800, 1900, 2000]) {
        svg.append("text").attr("x", x(t)).attr("y", H - 2).attr("text-anchor", t === 1607 ? "start" : "middle").attr("font-size", 10).attr("fill", css("--muted")).text(t);
      }
      const sp = el("div", "spark");
      sp.append(svg.node());
      box.append(sp);
    }
    const nat = D.stock.nat.o[o.id];
    const r = interp(nat, S.year);
    if (r) box.append(el("div", "meta", `${r.exact ? "" : "About "}${fmtInt(Math.round(r.v))} people born in ${o.name} lived in the US in ${S.year}${r.exact ? "" : ` (interpolated between ${r.a} and ${r.b})`}.`));
    const btn = el("button", "btn", "Clear selection");
    btn.type = "button";
    btn.addEventListener("click", () => selectOrigin(null));
    box.append(btn);
  }

  function selectOrigin(id) {
    S.origin = id;
    originBreaks = id ? originBreaksFor(id) : null;
    const ob = $("mode-origin");
    ob.textContent = id ? "Born in " + originById[id].name : "Born in…";
    if (id && stateOriginYears.length) S.mapMode = "origin";
    else if (!id && S.mapMode === "origin") S.mapMode = "share";
    syncSeg("map-mode", "mode", S.mapMode);
    drawAll();
  }

  // ---------- Composition chart ----------
  const compBox = $("comp");
  let comp = null;
  function layoutComp() {
    const W = Math.max(320, compBox.clientWidth || 900);
    const H = W < 600 ? 230 : 280;
    const m = { t: 26, r: 12, b: 40, l: 44 };
    compBox.replaceChildren();
    const svg = d3.select(compBox).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img");
    const x = d3.scaleLinear().domain([Y0, Y1]).range([m.l, W - m.r]);
    comp = { svg, W, H, m, x };
    const gGrid = svg.append("g").attr("class", "grid");
    const gArea = svg.append("g");
    const gAxis = svg.append("g").attr("class", "axis");
    const gEra = svg.append("g").attr("class", "era-band");
    const gEv = svg.append("g");
    const cursor = svg.append("line").attr("class", "cursor").attr("y1", m.t).attr("y2", H - m.b);
    const hover = svg.append("line").attr("class", "cursor-hover").attr("y1", m.t).attr("y2", H - m.b).attr("visibility", "hidden");
    const overlay = svg.append("rect").attr("x", m.l).attr("y", m.t).attr("width", W - m.l - m.r).attr("height", H - m.t - m.b).attr("fill", "transparent").style("cursor", "crosshair");
    Object.assign(comp, { gGrid, gArea, gAxis, gEra, gEv, cursor, hover, overlay });
    const yearAt = (evt) => clamp(Math.round(x.invert(d3.pointer(evt, svg.node())[0])), Y0, Y1);
    let dragging = false;
    overlay
      .on("pointerdown", (evt) => { dragging = true; overlay.node().setPointerCapture(evt.pointerId); stopPlay(); setYear(yearAt(evt)); })
      .on("pointerup", () => { dragging = false; })
      .on("pointermove", (evt) => {
        const yy = yearAt(evt);
        if (dragging) setYear(yy);
        hover.attr("visibility", "visible").attr("x1", x(yy)).attr("x2", x(yy));
        showCompTip(evt, yy);
      })
      .on("pointerleave", () => { hover.attr("visibility", "hidden"); hideTip(); });
    drawComp();
  }
  function compSeries() {
    return S.compSeries === "flow" ? flowGroupSeries : stockGroupSeries.filter((r) => r.year >= STOCK_FIRST);
  }
  function drawComp() {
    if (!comp) return;
    const { svg, W, H, m, x, gGrid, gArea, gAxis, gEra, gEv } = comp;
    const data = compSeries();
    const keys = groups.map((g) => g.id);
    const stack = d3.stack().keys(keys).offset(S.compScale === "share" ? d3.stackOffsetExpand : d3.stackOffsetNone);
    const series = stack(data);
    const ymax = S.compScale === "share" ? 1 : d3.max(series[series.length - 1], (d) => d[1]) || 1;
    const y = d3.scaleLinear().domain([0, ymax]).range([H - m.b, m.t]).nice();
    comp.y = y;
    const area = d3.area().curve(d3.curveMonotoneX).x((d) => x(d.data.year)).y0((d) => y(d[0])).y1((d) => y(d[1]));
    gArea.selectAll("path").data(series, (s) => s.key).join("path")
      .attr("d", (s) => area(s.map((d) => (isNaN(d[0]) ? Object.assign([0, 0], { data: d.data }) : d))))
      .attr("fill", (s) => groupColor[s.key]).attr("fill-opacity", 0.88)
      .attr("stroke", css("--panel")).attr("stroke-width", 0.8);
    const yt = S.compScale === "share" ? [0, 0.25, 0.5, 0.75, 1] : y.ticks(4);
    gGrid.selectAll("line").data(yt).join("line").attr("x1", m.l).attr("x2", W - m.r).attr("y1", (d) => y(d)).attr("y2", (d) => y(d));
    gAxis.replaceChildren && gAxis.selectAll("*").remove();
    gAxis.selectAll("text.yt").data(yt).join("text").attr("class", "yt").attr("x", m.l - 6).attr("y", (d) => y(d)).attr("dy", "0.32em").attr("text-anchor", "end")
      .text((d) => (S.compScale === "share" ? Math.round(d * 100) + "%" : compact(d)));
    const xt = W < 600 ? [1650, 1750, 1850, 1950] : [1607, 1650, 1700, 1750, 1800, 1850, 1900, 1950, 2000, 2024];
    gAxis.selectAll("text.xt").data(xt).join("text").attr("class", "xt").attr("x", (d) => x(d)).attr("y", H - m.b + 14).attr("text-anchor", (d) => (d === 1607 ? "start" : d === 2024 ? "end" : "middle")).text((d) => d);
    gAxis.append("line").attr("x1", m.l).attr("x2", W - m.r).attr("y1", H - m.b).attr("y2", H - m.b);
    if (S.compSeries === "stock") {
      gAxis.append("text").attr("x", x((Y0 + STOCK_FIRST) / 2)).attr("y", (m.t + H - m.b) / 2).attr("text-anchor", "middle").attr("fill", css("--muted"))
        .text(W < 600 ? `Birthplace first counted in ${STOCK_FIRST}` : `The census first asked people's birthplace in ${STOCK_FIRST}`);
    }
    // basis band
    gEra.selectAll("*").remove();
    const runs = basisRuns(S.compSeries);
    for (const r of runs) {
      const x0 = x(r.from - 0.5 < Y0 ? Y0 : r.from - 0.5), x1 = x(r.to + 0.5 > Y1 ? Y1 : r.to + 0.5);
      gEra.append("rect").attr("x", x0).attr("y", 4).attr("width", Math.max(0, x1 - x0 - 2)).attr("height", 4).attr("rx", 2)
        .attr("fill", r.cls === "official" ? css("--ink-2") : "none").attr("stroke", css("--ink-2")).attr("stroke-width", r.cls === "official" ? 0 : 1)
        .attr("stroke-dasharray", null);
      if (r.label && r.label.length * 6.2 < x1 - x0 - 4) gEra.append("text").attr("x", x0).attr("y", 20).text(r.label);
    }
    // events
    gEv.selectAll("*").remove();
    for (const e of D.events) {
      const ex = x(e.y);
      gEv.append("line").attr("class", "event-tick").attr("x1", ex).attr("x2", ex).attr("y1", H - m.b + 20).attr("y2", H - m.b + 28);
      gEv.append("rect").attr("class", "event-hit").attr("x", ex - 6).attr("y", H - m.b + 18).attr("width", 12).attr("height", 16)
        .on("pointerenter", (evt) => showTip(evt, (t) => { t.append(el("h4", null, e.label || String(e.y))); t.append(el("div", null, e.t)); }))
        .on("pointermove", moveTip).on("pointerleave", hideTip)
        .on("click", () => { stopPlay(); setYear(e.y); });
    }
    svg.attr("aria-label", (S.compSeries === "flow" ? "Arrivals" : "Immigrant population") + " by region of origin, " + (S.compScale === "share" ? "share" : "number") + ", over time");
    $("comp-title").textContent = S.compSeries === "flow" ? `Where arrivals came from, ${Y0}–${Y1}` : `Where immigrants living in the US were born, ${STOCK_FIRST}–${Y1}`;
    // legend
    const leg = $("comp-legend");
    leg.replaceChildren();
    for (const g of groups) {
      const s = el("span", "sw");
      const b = el("b");
      b.style.background = groupColor[g.id];
      s.append(b, el("span", null, g.name));
      leg.append(s);
    }
    const bandKey = el("span", "sw");
    const bk = el("b"); bk.style.cssText = `height:4px;background:${css("--ink-2")}`;
    const bk2 = el("b"); bk2.style.cssText = `height:4px;border:1px solid ${css("--ink-2")};background:none`;
    bandKey.append(bk, el("span", null, S.compSeries === "flow" ? "Official counts" : "Census or survey year"), bk2, el("span", null, S.compSeries === "flow" ? "Estimates" : "Interpolated"));
    leg.append(bandKey);
    updateCompCursor();
  }
  function basisRuns(kind) {
    const runs = [];
    if (kind === "flow") {
      let cur = null;
      for (let i = 0; i < NY; i++) {
        const c = D.flow.basis[i];
        const bi = basisInfo(c);
        if (!cur || cur.code !== c) { cur = { code: c, from: Y0 + i, to: Y0 + i, cls: bi.cls === "official" ? "official" : "est", label: bi.band || bi.label }; runs.push(cur); }
        else cur.to = Y0 + i;
      }
    } else {
      runs.push({ from: STOCK_FIRST, to: Y1, cls: "est", label: "Census every 10 years, interpolated between" });
      const acs = SY.filter((y, k) => D.stock.kind[k] === "acs");
      if (acs.length) { runs[0].to = acs[0] - 1; runs.push({ from: acs[0], to: Y1, cls: "official", label: "Annual survey" }); }
    }
    return runs;
  }
  function updateCompCursor() {
    if (!comp) return;
    comp.cursor.attr("x1", comp.x(S.year)).attr("x2", comp.x(S.year));
  }
  function showCompTip(evt, yy) {
    const data = S.compSeries === "flow" ? flowGroupSeries[yy - Y0] : stockGroupSeries[yy - Y0];
    showTip(evt, (t) => {
      t.append(el("h4", null, String(yy)));
      const tot = d3.sum(groups, (g) => data[g.id]);
      if (!tot) { t.append(el("div", "note", S.compSeries === "flow" ? "No arrivals recorded." : "No birthplace data before " + STOCK_FIRST + ".")); return; }
      for (const g of [...groups].reverse()) {
        const v = data[g.id];
        if (v > 0) tipRow(t, groupColor[g.id], g.name, (S.compScale === "share" ? pct(v / tot, 0) + " · " : "") + compact(v));
      }
      t.append(el("div", "note", (S.compSeries === "flow" ? "Total arrivals " : "Total born abroad ") + fmtInt(Math.round(tot)) + ". Click to jump here."));
    });
  }

  // ---------- World map ----------
  const worldBox = $("world");
  const worldFeats = topojson.feature(G.world, G.world.objects.countries).features;
  const isoToFeat = new Map(worldFeats.map((f, i) => [f.properties.iso3, i]));
  let world = null;
  const WORLD_BREAKS = [100, 1000, 5000, 20000, 50000, 100000];
  function layoutWorld() {
    const W = Math.max(320, worldBox.clientWidth || 900);
    const proj = d3.geoEqualEarth().rotate([-10, 0]).fitWidth(W, { type: "Sphere" });
    const path = d3.geoPath(proj);
    const b = path.bounds({ type: "Sphere" });
    const H = Math.ceil(b[1][1]);
    worldBox.replaceChildren();
    const svg = d3.select(worldBox).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img").attr("aria-label", "World map of where arrivals came from");
    svg.append("path").attr("class", "sphere").attr("d", path({ type: "Sphere" }));
    svg.append("path").attr("class", "graticule").attr("d", path(d3.geoGraticule10()));
    const gC = svg.append("g");
    gC.selectAll("path").data(worldFeats).join("path").attr("class", "country").attr("d", path)
      .on("pointerenter", (evt, f) => showWorldTip(evt, f))
      .on("pointermove", moveTip).on("pointerleave", hideTip)
      .on("click", (evt, f) => {
        const units = world.unitsFor.get(f.properties.iso3) || [];
        if (units.length) selectOrigin(units[0].id === S.origin ? null : units[0].id);
      });
    world = { svg, gC, path, unitsFor: new Map() };
    drawWorld();
  }
  function drawWorld() {
    if (!world) return;
    const y = S.year;
    const F = flowsAt(y);
    const val = new Map();
    const unitsFor = new Map();
    for (const d of F.list) {
      const o = originById[d.id];
      for (const iso of o.iso || []) {
        val.set(iso, (val.get(iso) || 0) + d.v);
        if (!unitsFor.has(iso)) unitsFor.set(iso, []);
        unitsFor.get(iso).push({ id: d.id, v: d.v });
      }
    }
    world.unitsFor = unitsFor;
    world.val = val;
    const c = seqColor(WORLD_BREAKS, "o");
    const land = css("--land");
    const selIso = new Set(S.origin ? originById[S.origin].iso || [] : []);
    world.gC.selectAll("path.country")
      .attr("fill", (f) => (f.properties.iso3 === "USA" ? css("--ink") : val.has(f.properties.iso3) ? c(val.get(f.properties.iso3)) : land))
      .classed("sel", (f) => selIso.has(f.properties.iso3));
    world.gC.selectAll("path.sel").raise();
    $("world-year").textContent = y;
    const bi = basisInfo(F.basis);
    const pill = $("world-basis");
    pill.className = "pill " + bi.cls;
    pill.lastChild.textContent = bi.label;
    const leg = $("world-legend");
    leg.replaceChildren();
    const ramp = el("span", "ramp");
    [0].concat(WORLD_BREAKS).forEach((b, k) => {
      const sp = el("span");
      const bb = el("b");
      bb.style.background = css("--o" + k);
      sp.append(bb, el("span", null, k === 0 ? "1+" : compact(b) + "+"));
      ramp.append(sp);
    });
    leg.append(ramp);
    const sw = el("span", "sw");
    const b1 = el("b"); b1.style.background = land;
    sw.append(b1, el("span", null, "None recorded"));
    leg.append(sw);
    const sw2 = el("span", "sw");
    const b2 = el("b"); b2.style.background = css("--ink");
    sw2.append(b2, el("span", null, "Destination"));
    leg.append(sw2);
    $("world-note").textContent = D.worldNote;
  }
  function showWorldTip(evt, f) {
    const iso = f.properties.iso3;
    showTip(evt, (t) => {
      t.append(el("h4", null, f.properties.name));
      if (iso === "USA") { t.append(el("div", "note", "Destination")); return; }
      const units = (world.unitsFor.get(iso) || []).slice().sort((a, b) => b.v - a.v);
      if (!units.length) { t.append(el("div", "note", `No arrivals recorded from here in ${S.year}.`)); return; }
      for (const u of units) {
        const o = originById[u.id];
        tipRow(t, groupColor[o.group], o.name, fmtInt(Math.round(u.v)));
        if ((o.iso || []).length > 1) t.append(el("div", "note", `Reported as one unit covering ${o.iso.length} present-day countries; each is shaded with the unit's total.`));
      }
      t.append(el("div", "note", "Click to follow this origin on the US map."));
    });
  }

  // ---------- Events ----------
  function drawEvents() {
    const box = $("events");
    if (!box.childElementCount) {
      for (const e of D.events) {
        const b = el("button", "event");
        b.type = "button";
        b.dataset.y = e.y;
        const et = el("span", "et");
        et.append(el("b", null, e.title), document.createTextNode(e.t));
        b.append(el("span", "ey", e.label || String(e.y)), et);
        b.addEventListener("click", () => { stopPlay(); setYear(e.y); });
        box.append(b);
      }
    }
    const cur = currentEvent(S.year, 1000);
    let curEl = null;
    for (const b of box.children) {
      const y = +b.dataset.y;
      b.classList.toggle("future", y > S.year);
      b.classList.toggle("past", y <= S.year);
      const isNow = cur && y === cur.y && b.querySelector(".et b").textContent === cur.title;
      b.classList.toggle("now", !!isNow);
      if (isNow) curEl = b;
    }
    if (curEl) {
      const top = curEl.offsetTop - box.offsetTop - box.clientHeight / 2 + curEl.clientHeight / 2;
      box.scrollTop = Math.max(0, top);
    }
  }
  function currentEvent(y, within) {
    let best = null;
    for (const e of D.events) if (e.y <= y && y - e.y <= within && (!best || e.y >= best.y)) best = e;
    return best;
  }

  // ---------- Headline ----------
  function drawHeadline() {
    const y = S.year;
    $("year").textContent = y;
    const F = flowsAt(y);
    const bi = basisInfo(F.basis);
    const est = bi.cls === "estimate";
    const lede = $("lede");
    lede.replaceChildren();
    if (F.total) {
      const n = est ? roundEst(F.total) : F.total;
      lede.append(document.createTextNode(`${est ? "An estimated " : ""}`));
      lede.append(el("strong", null, fmtInt(n)));
      lede.append(document.createTextNode(` ${n === 1 ? "person" : "people"} arrived in ${y}. `));
      const top = F.list.slice(0, 2);
      if (top.length) {
        lede.append(document.createTextNode("The largest group came from "));
        lede.append(el("strong", null, originById[top[0].id].name));
        lede.append(document.createTextNode(` (${pct(top[0].v / F.total, 0)})`));
        if (top[1]) {
          lede.append(document.createTextNode(", then "));
          lede.append(el("strong", null, originById[top[1].id].name));
          lede.append(document.createTextNode(` (${pct(top[1].v / F.total, 0)})`));
        }
        lede.append(document.createTextNode(". "));
      }
      const af = F.list.filter((d) => originById[d.id].forced).reduce((s, d) => s + d.v, 0);
      if (af > 0) lede.append(document.createTextNode(`About ${fmtInt(roundEst(af))} of them were enslaved Africans brought by force. `));
    } else {
      lede.append(document.createTextNode(`No arrivals are recorded for ${y}. `));
    }
    const nt = interp(D.stock.nat.total, y), np = interp(D.stock.nat.pop, y);
    if (nt && np) {
      lede.append(document.createTextNode(`${nt.exact ? "" : "About "}`));
      lede.append(el("strong", null, pct(nt.v / np.v)));
      lede.append(document.createTextNode(` of US residents were born abroad.`));
    }
    const ev = currentEvent(y, 12);
    const ctx = $("context");
    ctx.replaceChildren();
    if (ev) {
      ctx.append(el("b", null, (ev.label || ev.y) + " · " + ev.title + ". "), document.createTextNode(ev.t));
    }
  }

  // ---------- About ----------
  function drawAbout() {
    const box = $("about");
    box.replaceChildren();
    box.append(el("h2", null, "About the data"));
    for (const p of D.about.intro) box.append(el("p", null, p));
    const ts = el("div", "table-scroll");
    const table = el("table");
    const thead = el("thead");
    const hr = el("tr");
    for (const h of ["Years", "Arrivals by origin", "Immigrants living here"]) hr.append(el("th", null, h));
    thead.append(hr);
    const tb = el("tbody");
    for (const e of D.eras) {
      const tr = el("tr");
      tr.append(el("td", "num", e.years), el("td", null, e.flow), el("td", null, e.stock));
      tb.append(tr);
    }
    table.append(thead, tb);
    ts.append(table);
    box.append(ts);
    box.append(el("h2", null, "Caveats"));
    const ul = el("ul");
    for (const c of D.about.caveats) ul.append(el("li", null, c));
    box.append(ul);
    const det = el("details");
    const sum = el("summary");
    sum.append(el("h2", null, `Sources (${D.sources.length})`));
    det.append(sum);
    box.append(det);
    const ul2 = el("ul");
    for (const s of D.sources) {
      const li = el("li");
      li.append(document.createTextNode(s.cite + " "));
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
  }

  // ---------- controls ----------
  function syncSeg(id, attr, val) {
    for (const b of $(id).querySelectorAll("button")) b.setAttribute("aria-pressed", String(b.dataset[attr] === val));
  }
  function setYear(y) {
    y = clamp(y, Y0, Y1);
    if (y === S.year && drawn) return;
    S.year = y;
    $("slider").value = y;
    try { history.replaceState(null, "", "#" + y); } catch (e) { /* sandboxed */ }
    drawAll();
  }
  let drawn = false;
  function drawAll() {
    drawHeadline();
    drawUS();
    drawLedger();
    drawWorld();
    updateCompCursor();
    drawEvents();
    drawn = true;
  }
  function stopPlay() {
    if (!S.playing) return;
    S.playing = false;
    clearInterval(S.timer);
    $("play").setAttribute("aria-pressed", "false");
    $("play-label").textContent = "Play";
    $("play-icon").setAttribute("d", "M4 2.5v11l9-5.5z");
  }
  function startPlay() {
    if (S.year >= Y1) setYear(Y0);
    S.playing = true;
    $("play").setAttribute("aria-pressed", "true");
    $("play-label").textContent = "Pause";
    $("play-icon").setAttribute("d", "M3.5 2.5h3v11h-3zM9.5 2.5h3v11h-3z");
    const tick = () => {
      if (S.year >= Y1) { stopPlay(); return; }
      setYear(S.year + 1);
    };
    S.timer = setInterval(tick, +$("speed").value);
  }
  $("play").addEventListener("click", () => (S.playing ? stopPlay() : startPlay()));
  $("speed").addEventListener("change", () => { if (S.playing) { stopPlay(); startPlay(); } });
  $("back").addEventListener("click", () => { stopPlay(); setYear(S.year - 1); });
  $("fwd").addEventListener("click", () => { stopPlay(); setYear(S.year + 1); });
  $("slider").addEventListener("input", (e) => { stopPlay(); setYear(+e.target.value); });
  $("q").addEventListener("input", (e) => { S.query = e.target.value; drawLedger(); });
  $("more").addEventListener("click", () => { S.showAll = !S.showAll; drawLedger(); });
  $("map-mode").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    const mode = b.dataset.mode;
    if (mode === "origin" && !S.origin) {
      const F = flowsAt(S.year);
      const pick = F.list.length ? F.list[0].id : origins[0].id;
      selectOrigin(pick);
      return;
    }
    S.mapMode = mode;
    syncSeg("map-mode", "mode", mode);
    drawUS();
  });
  $("comp-series").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    S.compSeries = b.dataset.series;
    syncSeg("comp-series", "series", S.compSeries);
    drawComp();
  });
  $("comp-scale").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    S.compScale = b.dataset.scale;
    syncSeg("comp-scale", "scale", S.compScale);
    drawComp();
  });
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, select, textarea")) return;
    if (e.key === "ArrowRight" && !e.target.closest(".slider")) { stopPlay(); setYear(S.year + (e.shiftKey ? 10 : 1)); e.preventDefault(); }
    else if (e.key === "ArrowLeft" && !e.target.closest(".slider")) { stopPlay(); setYear(S.year - (e.shiftKey ? 10 : 1)); e.preventDefault(); }
    else if (e.key === " " && !e.target.closest("button")) { S.playing ? stopPlay() : startPlay(); e.preventDefault(); }
  });

  function drawTicks() {
    const box = $("ticks");
    box.replaceChildren();
    const marks = (box.clientWidth || 600) < 500 ? [1607, 1700, 1800, 1900, 2024] : [1607, 1650, 1700, 1750, 1800, 1850, 1900, 1950, 2000, 2024];
    for (const t of marks) {
      const s = el("span", null, t);
      // native range thumbs inset ~8px at each end
      const f = (t - Y0) / (Y1 - Y0);
      s.style.left = `calc(${f * 100}% + ${(0.5 - f) * 16}px)`;
      if (t === Y0) s.style.transform = "translateX(-8px)";
      if (t === Y1) s.style.transform = "translateX(calc(-100% + 8px))";
      box.append(s);
    }
  }

  // theme changes
  const onTheme = () => { readColors(); drawComp(); drawAll(); };
  try { matchMedia("(prefers-color-scheme: dark)").addEventListener("change", onTheme); } catch (e) { /* old browsers */ }
  new MutationObserver(onTheme).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  let rT = null;
  let lastW = 0;
  window.addEventListener("resize", () => {
    clearTimeout(rT);
    rT = setTimeout(() => {
      if (Math.abs(document.documentElement.clientWidth - lastW) < 4) return;
      lastW = document.documentElement.clientWidth;
      layoutUS(); layoutComp(); layoutWorld(); drawTicks(); drawAll();
    }, 150);
  });

  // ---------- boot ----------
  $("y-start").textContent = Y0;
  $("y-end").textContent = Y1;
  $("slider").min = Y0;
  $("slider").max = Y1;
  $("slider").value = S.year;
  lastW = document.documentElement.clientWidth;
  layoutUS();
  layoutComp();
  layoutWorld();
  drawTicks();
  drawAbout();
  drawAll();
})();
