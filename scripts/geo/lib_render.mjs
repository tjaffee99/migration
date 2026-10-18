// Small helper: render GeoJSON features to PNG via d3-geo (SVG) + headless Chromium (playwright-core).
// Uses the preinstalled browser at /opt/pw-browsers (never runs `playwright install`).
import { chromium } from 'playwright-core';
import { geoPath, geoAlbersUsa, geoArea } from 'd3-geo';

const EXEC = process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium';

const PALETTE = ['#8dd3c7','#ffffb3','#bebada','#fb8072','#80b1d3','#fdb462','#b3de69','#fccde5',
  '#d9d9d9','#bc80bd','#ccebc5','#ffed6f','#a6cee3','#b2df8a','#fb9a99','#fdbf6f','#cab2d6','#e5c494'];

export function hashColor(s) {
  let h = 0; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');

export function svgFor(features, { width = 1000, height = 620, projection, title = '', fill, label, stroke = '#333', bg = '#f4f1ea', extra = '' } = {}) {
  const proj = projection || geoAlbersUsa().fitExtent([[10, 30], [width - 10, height - 10]], { type: 'FeatureCollection', features });
  const path = geoPath(proj);
  let out = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`;
  out += `<rect width="100%" height="100%" fill="${bg}"/>`;
  for (const f of features) {
    const d = path(f); if (!d) continue;
    const fl = fill ? fill(f) : hashColor(f.properties?.id ?? '');
    out += `<path d="${d}" fill="${fl}" stroke="${stroke}" stroke-width="0.6" fill-rule="evenodd"><title>${esc(f.properties?.name ?? '')}</title></path>`;
  }
  if (label) {
    for (const f of features) {
      const t = label(f); if (!t) continue;
      const c = path.centroid(f); if (!c || !isFinite(c[0])) continue;
      out += `<text x="${c[0].toFixed(1)}" y="${c[1].toFixed(1)}" font-family="sans-serif" font-size="9" text-anchor="middle" fill="#111" stroke="#fff" stroke-width="2" paint-order="stroke">${esc(t)}</text>`;
    }
  }
  out += extra;
  out += `<text x="12" y="22" font-family="sans-serif" font-size="16" font-weight="bold" fill="#111">${esc(title)}</text></svg>`;
  return out;
}

export async function svgsToPngs(items) {
  // items: [{svg, file, width, height}]
  const browser = await chromium.launch({ executablePath: EXEC, args: ['--no-sandbox'] });
  try {
    const page = await browser.newPage();
    for (const it of items) {
      await page.setViewportSize({ width: it.width || 1000, height: it.height || 620 });
      await page.setContent(`<!doctype html><html><body style="margin:0">${it.svg}</body></html>`);
      await page.screenshot({ path: it.file, clip: { x: 0, y: 0, width: it.width || 1000, height: it.height || 620 } });
    }
  } finally { await browser.close(); }
}

// d3-geo uses spherical winding (exterior rings clockwise). Flip any polygon whose
// spherical area exceeds a hemisphere (i.e. it was wound the "wrong" way).
export function fixWinding(f) {
  const g = f.geometry; if (!g) return f;
  const fixPoly = (rings) => {
    const a = geoArea({ type: 'Polygon', coordinates: rings });
    return a > 2 * Math.PI ? rings.map(r => r.slice().reverse()) : rings;
  };
  if (g.type === 'Polygon') g.coordinates = fixPoly(g.coordinates);
  else if (g.type === 'MultiPolygon') g.coordinates = g.coordinates.map(fixPoly);
  return f;
}
