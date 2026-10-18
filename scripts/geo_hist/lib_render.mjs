// Shared rendering helpers for the historical world layer checks:
// d3-geo -> SVG string -> PNG via the preinstalled headless Chromium (playwright-core; never downloads a browser).
import { chromium } from 'playwright-core';
import { geoPath, geoEqualEarth, geoGraticule10 } from 'd3-geo';

const EXEC = process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium';

const PALETTE = ['#8dd3c7', '#ffffb3', '#bebada', '#fb8072', '#80b1d3', '#fdb462', '#b3de69', '#fccde5',
  '#bc80bd', '#ccebc5', '#ffed6f', '#a6cee3', '#b2df8a', '#fb9a99', '#fdbf6f', '#cab2d6', '#e5c494'];

export function hashColor(s) {
  let h = 0; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

export const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');

// The page's projection: Equal Earth centred on 90°W, fitted to the sphere at the given width.
export function pageProjection(width) {
  const p = geoEqualEarth().rotate([90, 0]);
  p.fitWidth(width, { type: 'Sphere' });
  return p;
}

export async function svgsToPngs(items) {
  const browser = await chromium.launch({ executablePath: EXEC, args: ['--no-sandbox'] });
  try {
    const page = await browser.newPage();
    for (const it of items) {
      await page.setViewportSize({ width: it.width, height: it.height });
      await page.setContent(`<!doctype html><html><body style="margin:0">${it.svg}</body></html>`);
      await page.screenshot({ path: it.file, clip: { x: 0, y: 0, width: it.width, height: it.height } });
    }
  } finally { await browser.close(); }
}

// features: GeoJSON features; opts.fill(f), opts.label(f) optional.
export function worldSvg(features, { width = 1200, projection, title = '', fill, label, land, stroke = '#333',
  strokeWidth = 0.35, bg = '#dfe9f2', gaps = false, legend = [] } = {}) {
  const proj = projection || pageProjection(width);
  const path = geoPath(proj);
  const height = Math.ceil(path.bounds({ type: 'Sphere' })[1][1]) + 2;
  let out = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`;
  out += `<rect width="100%" height="100%" fill="#fff"/>`;
  out += `<path d="${path({ type: 'Sphere' })}" fill="${gaps ? '#000' : bg}" stroke="#999" stroke-width="0.5"/>`;
  if (!gaps) out += `<path d="${path(geoGraticule10())}" fill="none" stroke="#c9d6e2" stroke-width="0.3"/>`;
  if (land) out += `<path d="${path(land)}" fill="${gaps ? '#ff00ff' : '#bdbdbd'}" stroke="none"/>`;
  for (const f of features) {
    const d = path(f); if (!d) continue;
    const fl = gaps ? '#fff' : (fill ? fill(f) : hashColor(f.properties?.id ?? ''));
    out += `<path d="${d}" fill="${fl}" ${gaps ? 'stroke="none"' : `fill-opacity="0.85" stroke="${stroke}" stroke-width="${strokeWidth}"`}><title>${esc(f.properties?.name ?? '')}</title></path>`;
  }
  if (label) {
    for (const f of features) {
      const t = label(f, path); if (!t) continue;
      const c = path.centroid(f); if (!c || !isFinite(c[0])) continue;
      out += `<text x="${c[0].toFixed(1)}" y="${c[1].toFixed(1)}" font-family="sans-serif" font-size="7.5" text-anchor="middle" fill="#111" stroke="#fff" stroke-width="1.8" paint-order="stroke">${esc(t)}</text>`;
    }
  }
  legend.forEach((t, i) => {
    out += `<text x="10" y="${height - 10 - 13 * (legend.length - 1 - i)}" font-family="sans-serif" font-size="11" fill="#111" stroke="#fff" stroke-width="2.5" paint-order="stroke">${esc(t)}</text>`;
  });
  out += `<text x="10" y="20" font-family="sans-serif" font-size="15" font-weight="bold" fill="#111" stroke="#fff" stroke-width="3" paint-order="stroke">${esc(title)}</text></svg>`;
  return { svg: out, width, height };
}
