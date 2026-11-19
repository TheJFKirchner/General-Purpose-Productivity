#!/usr/bin/env node

/**
 * Checks the ECharts charts in a presentation: valid JSON, and the slide-chart limits
 * in references/charts.md (few points, few series, one highlighted item).
 * No dependencies.
 *
 * Usage: node check-charts.js <path-to-html>
 */

const fs = require('fs');

const MAX_POINTS = 12;      // categories
const MAX_TIME_POINTS = 24; // a time axis keeps the source's period
const MAX_SERIES = 4;
const MAX_SLICES = 5;

function lineOf(html, index) {
  return (html.slice(0, index).match(/\n/g) || []).length + 1;
}

function slideIdAt(html, index) {
  const before = html.slice(0, index);
  const all = [...before.matchAll(/<section\b[^>]*\bid="([^"]+)"/g)];
  return all.length ? all[all.length - 1][1] : 'unknown slide';
}

function hasOwnColour(item) {
  return item && typeof item === 'object' && !Array.isArray(item) && item.itemStyle && item.itemStyle.color;
}

// Period labels: Jan, Jan 25, Nov 2025, 2025-11, Q3 25, 2025 Q3, 2025
const PERIOD = /^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?(\s*'?\d{2,4})?$|^\d{4}[-\/]\d{1,2}$|^q[1-4]\s*'?\d{2,4}$|^\d{4}\s*q[1-4]$|^\d{4}$/i;

function isTimeAxis(option) {
  return [].concat(option.xAxis || [], option.yAxis || []).some(a => a && a.type === 'category' && Array.isArray(a.data) && a.data.length &&
    a.data.filter(d => PERIOD.test(String(d && d.value !== undefined ? d.value : d).trim())).length >= a.data.length / 2);
}

function checkChart(option) {
  const errors = [];
  const warnings = [];
  const series = Array.isArray(option.series) ? option.series : option.series ? [option.series] : [];
  const timeAxis = isTimeAxis(option);

  if (series.length === 0) {
    errors.push("no 'series'");
    return { errors, warnings };
  }
  if (series.length > MAX_SERIES) {
    warnings.push(`${series.length} series; keep to ${MAX_SERIES} or fewer`);
  }
  series.forEach((s, i) => {
    const name = `series ${i + 1}`;
    if (!s.type) errors.push(`${name} has no 'type'`);
    if (!Array.isArray(s.data) || s.data.length === 0) {
      errors.push(`${name} has no 'data'`);
      return;
    }
    if (s.type === 'heatmap') return; // cells, not points
    const limit = s.type === 'pie' ? MAX_SLICES : timeAxis ? MAX_TIME_POINTS : MAX_POINTS;
    if (s.data.length > limit) {
      warnings.push(timeAxis
        ? `${name} has ${s.data.length} periods; up to ${limit} fit a full-width chart. Over that, use a coarser period (quarters); never cut the window`
        : `${name} has ${s.data.length} points; keep to ${limit} or fewer and group the rest as "Other"`);
    }
  });

  // One item should stand out: a data item with its own colour, or (with several series) series with their own colours.
  const itemHighlight = series.some(s => Array.isArray(s.data) && s.data.some(hasOwnColour));
  const seriesColoured = series.length > 1 && series.every(s => (s.itemStyle && s.itemStyle.color) || (s.lineStyle && s.lineStyle.color));
  const usesVisualMap = !!option.visualMap;
  // A single line is its own highlight. A single bar or pie series with several items needs one picked out.
  const single = series.length === 1 ? series[0] : null;
  const singleNeedsPick = single && ['bar', 'pie', 'scatter'].includes(single.type) && Array.isArray(single.data) && single.data.length > 1;
  const multiNeedsPick = series.length > 1;
  if (!itemHighlight && !seriesColoured && !usesVisualMap && (singleNeedsPick || multiNeedsPick)) {
    warnings.push('nothing is highlighted; give the item the headline is about var(--blue) (ignore on the muted half of a two-chart comparison)');
  }
  const isPrimary = item => hasOwnColour(item) && /--(blue|primary-color)/.test(String(item.itemStyle.color));
  series.forEach((s, i) => {
    const n = Array.isArray(s.data) ? s.data.filter(isPrimary).length : 0;
    if (n > 1 && n > s.data.length / 2) {
      warnings.push(`series ${i + 1} highlights ${n} of ${s.data.length} items; a highlight on most items is not a highlight`);
    }
  });
  if (option.tooltip) {
    warnings.push("'tooltip' is set by the deck (a light one-line hover); remove it from the chart JSON");
  }
  if (option.toolbox || option.dataZoom || option.timeline || option.brush) {
    warnings.push('toolbox, dataZoom, timeline and brush are for exploring; remove them');
  }
  return { errors, warnings };
}

function main() {
  const htmlPath = process.argv[2];
  if (!htmlPath) {
    console.error('Usage: node check-charts.js <path-to-html>');
    process.exit(1);
  }
  if (!fs.existsSync(htmlPath)) {
    console.error(`Error: File not found: ${htmlPath}`);
    process.exit(1);
  }

  // Only the slides: the engine script below them mentions chart markup in comments.
  const full = fs.readFileSync(htmlPath, 'utf-8');
  const end = full.indexOf('<!-- SLIDES:END -->');
  const html = end === -1 ? full : full.slice(0, end);
  const pattern = /<div\b[^>]*\bdata-echart\b[^>]*>\s*(?:<script type="application\/json">([\s\S]*?)<\/script>)?/g;
  const charts = [...html.matchAll(pattern)];

  console.log(`Checking charts in: ${htmlPath}\n`);
  if (/<canvas\b[^>]*data-chart=/.test(html)) {
    console.log('ERROR: found <canvas data-chart>. This deck uses ECharts: <div class="chart" data-echart>.\n');
  }
  const controls = [...html.matchAll(/<(select|input|button|details|iframe|textarea)\b/g)];
  controls.forEach(m => {
    console.log(`ERROR  ${slideIdAt(html, m.index)}, line ${lineOf(html, m.index)}: <${m[1]}> on a slide. A slide shows one fixed cut; no controls or embedded pages.`);
  });
  if (charts.length === 0) {
    console.log('No charts found in presentation.');
    if (controls.length) process.exit(1);
    return;
  }

  let totalErrors = 0;
  let totalWarnings = 0;

  charts.forEach((m, index) => {
    const where = `Chart ${index + 1} (${slideIdAt(html, m.index)}, line ${lineOf(html, m.index)})`;
    let errors = [];
    let warnings = [];
    if (m[1] === undefined) {
      errors.push('no <script type="application/json"> directly inside the chart div');
    } else {
      try {
        ({ errors, warnings } = checkChart(JSON.parse(m[1])));
      } catch (e) {
        errors.push(`invalid JSON: ${e.message}`);
      }
    }
    if (!/class="[^"]*\bchart\b/.test(m[0])) {
      warnings.push('chart div has no class="chart"; it will not size to its space');
    }
    if (errors.length === 0 && warnings.length === 0) {
      console.log(`OK     ${where}`);
    }
    errors.forEach(e => console.log(`ERROR  ${where}: ${e}`));
    warnings.forEach(w => console.log(`WARN   ${where}: ${w}`));
    totalErrors += errors.length;
    totalWarnings += warnings.length;
  });

  console.log(`\nTotal: ${charts.length} charts, ${totalErrors} errors, ${totalWarnings} warnings`);
  if (totalErrors > 0 || controls.length) process.exit(1);
}

main();
