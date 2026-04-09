"""Build chord.html with 3 tabs: Family×Family, Book×Family, Narrator×Book.
Data embedded inline (no fetch needed)."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'app' / 'data'
OUT  = ROOT / 'app' / 'chord.html'

# ── Load existing matrices ────────────────────────────────────────────────────
d = json.load(open(DATA / 'chord_matrices.json', encoding='utf-8'))

# ── Build narrator × book matrix from isnad_graph.json ────────────────────────
isnad = json.load(open(DATA / 'isnad_graph.json', encoding='utf-8'))
isnad_books = list(isnad.keys())

narr_by_book = {}
global_count = Counter()
for bk in isnad_books:
    nodes = isnad[bk]['nodes']
    narr_by_book[bk] = {n['id']: n['count'] for n in nodes}
    for n in nodes:
        global_count[n['id']] += n['count']

# Hybrid selection: top 20 global + ensure at least 1 per book
selected = set(n for n, _ in global_count.most_common(20))
for bk in isnad_books:
    if narr_by_book[bk]:
        top_in_book = max(narr_by_book[bk], key=narr_by_book[bk].get)
        selected.add(top_in_book)
narr_keys = sorted(selected, key=lambda n: -global_count[n])

# Build matrix: narrators (rows) × books (columns) → bipartite
narr_book_matrix = []
for n in narr_keys:
    row = [narr_by_book[bk].get(n, 0) for bk in isnad_books]
    narr_book_matrix.append(row)

d['narr_keys'] = narr_keys
d['narr_book_keys'] = isnad_books
d['narr_book_matrix'] = narr_book_matrix

# ── Count total hadiths for subtitle ──────────────────────────────────────────
total_hadiths = 112_221  # from verified corpus count

data_js = json.dumps(d, ensure_ascii=False, separators=(',', ':'))

# ── HTML template ─────────────────────────────────────────────────────────────
html = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Al-Itqan — Chord Graphs</title>
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: "Segoe UI", sans-serif;
  background: #0d0d1a; color: #ddd;
  min-height: 100vh;
  display: flex; flex-direction: column; align-items: center;
  padding: 24px 16px;
}
h1 { color: #f0c060; font-size: 1.5rem; margin-bottom: 4px; }
.sub { color: #666; font-size: .85rem; margin-bottom: 22px; }
.tabs { display: flex; gap: 6px; margin-bottom: 20px; flex-wrap: wrap; justify-content: center; }
.tab {
  padding: 8px 22px; border-radius: 20px; border: 1px solid #333;
  cursor: pointer; font-size: .88rem; color: #aaa;
  background: #12121f; transition: all .2s;
}
.tab.active { background: #f0c060; color: #111; border-color: #f0c060; font-weight: 600; }
.panel { display: none; width: 100%; max-width: 960px; flex-direction: column; align-items: center; }
.panel.active { display: flex; }
#tooltip {
  position: fixed; pointer-events: none;
  background: rgba(10,10,25,.96); border: 1px solid #444;
  border-radius: 8px; padding: 10px 14px;
  font-size: .82rem; line-height: 1.65; max-width: 260px;
  z-index: 999; display: none;
}
#tooltip strong { color: #f0c060; display: block; margin-bottom: 2px; }
.num { color: #7eb3f0; }
.info-bar {
  background: #12121f; border: 1px solid #2a2a3a;
  border-radius: 8px; padding: 9px 16px; font-size: .78rem;
  color: #777; margin-bottom: 14px; text-align: center; width: 100%;
}
.info-bar strong { color: #aaa; }
.legend {
  display: flex; flex-wrap: wrap; gap: 6px 14px;
  margin-top: 12px; justify-content: center; max-width: 900px;
}
.leg { display: flex; align-items: center; gap: 5px; font-size: .72rem; color: #999;
       cursor: pointer; padding: 2px 5px; border-radius: 3px; }
.leg:hover { background: #1a1a30; }
.swatch { width: 11px; height: 11px; border-radius: 2px; flex-shrink: 0; }
</style>
</head>
<body>
<h1>Al-Itqan &middot; Chord Graphs</h1>
<div class="sub">Interactive thematic overlap &middot; """ + f'{total_hadiths:,}' + r""" hadiths &middot; 39 families &middot; 18 books</div>

<div class="tabs" id="tab-bar">
  <div class="tab active" data-tab="fam">Family &times; Family Overlap</div>
  <div class="tab"        data-tab="book">Book &times; Family Distribution</div>
  <div class="tab"        data-tab="narr">Narrator &times; Book</div>
</div>

<div class="panel active" id="panel-fam">
  <div class="info-bar">
    <strong>Hover</strong> an arc to see overlaps &middot;
    <strong>Click</strong> an arc to isolate its connections &middot;
    click background to reset &middot;
    <span style="color:#f0a060">&#9632;</span> = new family
  </div>
  <svg id="svg-fam"></svg>
  <div class="legend" id="leg-fam"></div>
</div>

<div class="panel" id="panel-book">
  <div class="info-bar">
    <span style="color:#a8ccf0">&#9632;</span> Blues = books &middot;
    <span style="color:#f0c080">&#9632;</span> Oranges = top 15 families &middot;
    chord width = shared hadiths &middot; hover / click to explore
  </div>
  <svg id="svg-book"></svg>
  <div class="legend" id="leg-book"></div>
</div>

<div class="panel" id="panel-narr">
  <div class="info-bar">
    <span style="color:#c8a0e8">&#9632;</span> Purple = narrators &middot;
    <span style="color:#a8ccf0">&#9632;</span> Blue = books &middot;
    chord width = narrations in that book &middot; hover / click to explore
  </div>
  <svg id="svg-narr"></svg>
  <div class="legend" id="leg-narr"></div>
</div>

<div id="tooltip"></div>

<script>
const DATA = """ + data_js + r""";

// ── Tab switching with full reset ────────────────────────────────────────────
const TAB_NAMES = ["fam", "book", "narr"];
const resetFns = {};  // each chart registers its reset function here

document.getElementById("tab-bar").addEventListener("click", function(e) {
  const tab = e.target.closest("[data-tab]");
  if (!tab) return;
  const name = tab.dataset.tab;
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  document.getElementById("panel-" + name).classList.add("active");
  // Reset ALL charts when switching tabs
  TAB_NAMES.forEach(n => { if (resetFns[n]) resetFns[n](); });
  hideTip();
});

const tip = document.getElementById("tooltip");
function showTip(html, e) { tip.innerHTML = html; tip.style.display = "block"; moveTip(e); }
function moveTip(e) {
  tip.style.left = Math.min(e.clientX + 14, window.innerWidth - 275) + "px";
  tip.style.top  = Math.max(e.clientY - 6, 8) + "px";
}
function hideTip() { tip.style.display = "none"; }
const fmt = d3.format(",");

// ── FAMILY x FAMILY CHORD ────────────────────────────────────────────────────
(function() {
  const { family_keys, family_labels, family_matrix, family_totals } = DATA;
  const N = family_keys.length;
  const NEW = new Set(["end_of_times","jihad","statecraft","family_law"]);
  const palette = d3.quantize(t => d3.interpolateRainbow(t * .88 + .05), N);

  const W = 800, r0 = 278, r1 = 326;
  const svg = d3.select("#svg-fam")
    .attr("viewBox", `${-W/2} ${-W/2} ${W} ${W}`)
    .attr("width", "100%")
    .style("max-height", "800px");

  const chordL  = d3.chord().padAngle(.012).sortSubgroups(d3.descending)(family_matrix);
  const arcPath = d3.arc().innerRadius(r0).outerRadius(r1);
  const ribPath = d3.ribbon().radius(r0 - 1);

  let active = null;

  const ribbons = svg.append("g").selectAll("path")
    .data(chordL).join("path")
    .attr("d", ribPath)
    .attr("fill", d => palette[d.source.index])
    .attr("fill-opacity", .52)
    .attr("stroke", d => d3.color(palette[d.source.index]).darker(.5))
    .attr("stroke-width", .4)
    .style("cursor", "pointer")
    .on("mouseover", function(e, d) {
      if (active !== null) return;
      d3.select(this).attr("fill-opacity", .88);
      showTip(
        "<strong>" + family_labels[d.source.index] + "</strong>" +
        "<span style='color:#aaa'> \u2194 </span>" +
        "<strong>" + family_labels[d.target.index] + "</strong><br>" +
        "<span class='num'>" + fmt(Math.round(d.source.value)) + "</span> shared hadiths", e);
    })
    .on("mousemove", moveTip)
    .on("mouseout", function() {
      if (active !== null) return;
      d3.select(this).attr("fill-opacity", .52); hideTip();
    });

  function resetAll() {
    active = null;
    ribbons.attr("fill-opacity", .52).attr("display", null);
    arcPaths.attr("fill-opacity", 1);
    hideTip();
  }
  resetFns.fam = resetAll;
  svg.on("click", resetAll);

  const grps = svg.append("g").selectAll("g")
    .data(chordL.groups).join("g")
    .style("cursor", "pointer")
    .on("click", function(e, d) {
      e.stopPropagation();
      if (active === d.index) { resetAll(); return; }
      active = d.index;
      ribbons
        .attr("display", c =>
          (c.source.index === d.index || c.target.index === d.index) ? null : "none")
        .attr("fill-opacity", .82);
      arcPaths.attr("fill-opacity", a => {
        if (a.index === d.index) return 1;
        return chordL.some(c =>
          (c.source.index === d.index && c.target.index === a.index) ||
          (c.target.index === d.index && c.source.index === a.index)) ? 1 : .18;
      });
    })
    .on("mouseover", function(e, d) {
      if (active !== null) return;
      ribbons.attr("fill-opacity", c =>
        (c.source.index === d.index || c.target.index === d.index) ? .88 : .1);
      const top = family_matrix[d.index]
        .map((v, i) => ({ i, v }))
        .filter(x => x.i !== d.index && x.v > 0)
        .sort((a, b) => b.v - a.v).slice(0, 4)
        .map(x => family_labels[x.i] + ": <span class='num'>" + fmt(x.v) + "</span>")
        .join("<br>");
      const star = NEW.has(family_keys[d.index])
        ? " <span style='color:#e74c3c;font-size:.72rem'>NEW</span>" : "";
      showTip(
        "<strong>" + family_labels[d.index] + star + "</strong><br>" +
        "<span class='num'>" + fmt(family_totals[d.index]) + "</span> hadiths<br><br>" +
        "Top overlaps:<br>" + top, e);
    })
    .on("mousemove", moveTip)
    .on("mouseout", function() {
      if (active !== null) return;
      ribbons.attr("fill-opacity", .52); hideTip();
    });

  const arcPaths = grps.append("path")
    .attr("d", arcPath)
    .attr("fill", d => palette[d.index])
    .attr("stroke", d => d3.color(palette[d.index]).darker(.8))
    .attr("stroke-width", .5);

  grps.append("text")
    .each(d => { d.angle = (d.startAngle + d.endAngle) / 2; })
    .attr("transform", d =>
      "rotate(" + (d.angle * 180 / Math.PI - 90) + ")" +
      " translate(" + (r1 + 7) + ")" +
      (d.angle > Math.PI ? " rotate(180)" : ""))
    .attr("text-anchor", d => d.angle > Math.PI ? "end" : "start")
    .attr("fill", d => NEW.has(family_keys[d.index]) ? "#f0a060" : "#ccc")
    .attr("font-size", d => (d.endAngle - d.startAngle) > .13 ? 10 : 0)
    .text(d => family_labels[d.index].split(",")[0].trim().slice(0, 20));

  const legEl = document.getElementById("leg-fam");
  family_keys.forEach((k, i) => {
    const div = document.createElement("div");
    div.className = "leg";
    div.innerHTML = "<div class='swatch' style='background:" + palette[i] + "'></div>" +
      family_labels[i].split(",")[0].trim().slice(0, 22);
    if (NEW.has(k)) { div.style.color = "#f0a060"; div.style.fontWeight = "600"; }
    legEl.appendChild(div);
  });
})();

// ── BOOK x FAMILY CHORD ──────────────────────────────────────────────────────
(function() {
  const { book_keys, family_keys_top15, book_family_matrix } = DATA;
  const nB = book_keys.length, nF = family_keys_top15.length;
  const N  = nB + nF;

  const matrix = Array.from({ length: N }, (_, r) =>
    Array.from({ length: N }, (_, c) => {
      if (r < nB && c >= nB) return book_family_matrix[r][c - nB] || 0;
      if (c < nB && r >= nB) return book_family_matrix[c][r - nB] || 0;
      return 0;
    }));

  const SHORT = {
    musannaf_ibnabi_shaybah: "Musannaf IAS",
    mishkat_almasabih: "Mishkat",
    riyad_assalihin: "Riyad Salihin",
    aladab_almufrad: "Adab Mufrad",
    shamail_muhammadiyah: "Shamail",
    bulugh_almaram: "Bulugh",
    shahwaliullah40: "Shah Wali 40",
    nawawi40: "Nawawi 40",
    qudsi40: "Qudsi 40",
  };
  const cap = s => s.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  const bookLabels = book_keys.map(b => SHORT[b] || cap(b));
  const famLabels  = family_keys_top15.map(f => cap(f));
  const labels     = [...bookLabels, ...famLabels];

  const bookPal = d3.quantize(t => d3.interpolateBlues(.35 + t * .55), nB);
  const famPal  = d3.quantize(t => d3.interpolateOranges(.4  + t * .5),  nF);
  const allC    = [...bookPal, ...famPal];

  const W = 860, r0 = 308, r1 = 352;
  const svg = d3.select("#svg-book")
    .attr("viewBox", `${-W/2} ${-W/2} ${W} ${W}`)
    .attr("width", "100%")
    .style("max-height", "860px");

  const chordL  = d3.chord().padAngle(.009).sortSubgroups(d3.descending)(matrix);
  const arcPath = d3.arc().innerRadius(r0).outerRadius(r1);
  const ribPath = d3.ribbon().radius(r0 - 1);

  let active = null;

  const ribbons = svg.append("g").selectAll("path")
    .data(chordL).join("path")
    .attr("d", ribPath)
    .attr("fill", d => allC[d.source.index])
    .attr("fill-opacity", .48)
    .attr("stroke", d => d3.color(allC[d.source.index]).darker(.6))
    .attr("stroke-width", .4)
    .style("cursor", "pointer")
    .on("mouseover", function(e, d) {
      if (active !== null) return;
      d3.select(this).attr("fill-opacity", .88);
      showTip(
        "<strong>" + labels[d.source.index] + "</strong>" +
        "<span style='color:#aaa'> \u2194 </span>" +
        "<strong>" + labels[d.target.index] + "</strong><br>" +
        "<span class='num'>" + fmt(Math.round(d.source.value)) + "</span> hadiths", e);
    })
    .on("mousemove", moveTip)
    .on("mouseout", function() {
      if (active !== null) return;
      d3.select(this).attr("fill-opacity", .48); hideTip();
    });

  function resetAll() {
    active = null;
    ribbons.attr("fill-opacity", .48).attr("display", null);
    arcPaths.attr("fill-opacity", 1);
    hideTip();
  }
  resetFns.book = resetAll;
  svg.on("click", resetAll);

  const grps = svg.append("g").selectAll("g")
    .data(chordL.groups).join("g")
    .style("cursor", "pointer")
    .on("click", function(e, d) {
      e.stopPropagation();
      if (active === d.index) { resetAll(); return; }
      active = d.index;
      ribbons
        .attr("display", c =>
          (c.source.index === d.index || c.target.index === d.index) ? null : "none")
        .attr("fill-opacity", .82);
      arcPaths.attr("fill-opacity", a => {
        if (a.index === d.index) return 1;
        return chordL.some(c =>
          (c.source.index === d.index && c.target.index === a.index) ||
          (c.target.index === d.index && c.source.index === a.index)) ? 1 : .15;
      });
    })
    .on("mouseover", function(e, d) {
      if (active !== null) return;
      ribbons.attr("fill-opacity", c =>
        (c.source.index === d.index || c.target.index === d.index) ? .88 : .1);
      const isBook = d.index < nB;
      const total  = matrix[d.index].reduce((s, v) => s + v, 0);
      const top = (isBook
        ? famLabels.map((f, j) => ({ label: f, v: book_family_matrix[d.index][j] || 0 }))
        : bookLabels.map((b, i) => ({ label: b, v: book_family_matrix[i][d.index - nB] || 0 }))
      ).sort((a, b) => b.v - a.v).slice(0, 4)
       .map(x => x.label + ": <span class='num'>" + fmt(x.v) + "</span>").join("<br>");
      showTip(
        "<strong>" + labels[d.index] + "</strong>" +
        "<span style='color:#777;font-size:.72rem'> " + (isBook ? "BOOK" : "FAMILY") + "</span><br>" +
        "<span class='num'>" + fmt(total) + "</span> connections<br><br>" +
        "Top links:<br>" + top, e);
    })
    .on("mousemove", moveTip)
    .on("mouseout", function() {
      if (active !== null) return;
      ribbons.attr("fill-opacity", .48); hideTip();
    });

  const arcPaths = grps.append("path")
    .attr("d", arcPath)
    .attr("fill", d => allC[d.index])
    .attr("stroke", d => d3.color(allC[d.index]).darker(.8))
    .attr("stroke-width", .5);

  grps.append("text")
    .each(d => { d.angle = (d.startAngle + d.endAngle) / 2; })
    .attr("transform", d =>
      "rotate(" + (d.angle * 180 / Math.PI - 90) + ")" +
      " translate(" + (r1 + 7) + ")" +
      (d.angle > Math.PI ? " rotate(180)" : ""))
    .attr("text-anchor", d => d.angle > Math.PI ? "end" : "start")
    .attr("fill", d => d.index < nB ? "#a8ccf0" : "#f0c080")
    .attr("font-size", d => (d.endAngle - d.startAngle) > .055 ? 10 : 0)
    .attr("font-weight", d => d.index >= nB ? "600" : "normal")
    .text(d => labels[d.index].slice(0, 16));

  const legEl = document.getElementById("leg-book");
  const bh = document.createElement("div");
  bh.style.cssText = "width:100%;font-size:.72rem;color:#7eb3f0;font-weight:700;margin-bottom:3px;padding-left:4px;";
  bh.textContent = "BOOKS"; legEl.appendChild(bh);
  book_keys.forEach((k, i) => {
    const div = document.createElement("div");
    div.className = "leg";
    div.innerHTML = "<div class='swatch' style='background:" + bookPal[i] + "'></div>" + bookLabels[i];
    legEl.appendChild(div);
  });
  const fh = document.createElement("div");
  fh.style.cssText = "width:100%;font-size:.72rem;color:#f0a060;font-weight:700;margin-top:8px;margin-bottom:3px;padding-left:4px;";
  fh.textContent = "FAMILIES"; legEl.appendChild(fh);
  family_keys_top15.forEach((k, i) => {
    const div = document.createElement("div");
    div.className = "leg";
    div.innerHTML = "<div class='swatch' style='background:" + famPal[i] + "'></div>" + famLabels[i];
    legEl.appendChild(div);
  });
})();

// ── NARRATOR x BOOK CHORD ────────────────────────────────────────────────────
(function() {
  const { narr_keys, narr_book_keys, narr_book_matrix } = DATA;
  const nN = narr_keys.length, nB = narr_book_keys.length;
  const N  = nN + nB;

  // Bipartite matrix: narrators in rows 0..nN-1, books in rows nN..N-1
  const matrix = Array.from({ length: N }, (_, r) =>
    Array.from({ length: N }, (_, c) => {
      if (r < nN && c >= nN) return narr_book_matrix[r][c - nN] || 0;
      if (c < nN && r >= nN) return narr_book_matrix[c][r - nN] || 0;
      return 0;
    }));

  const SHORT = {
    musannaf_ibnabi_shaybah: "Musannaf IAS",
    mishkat_almasabih: "Mishkat",
  };
  const cap = s => s.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  const bookLabels = narr_book_keys.map(b => SHORT[b] || cap(b));
  const labels = [...narr_keys, ...bookLabels];

  const narrPal = d3.quantize(t => d3.interpolatePurples(.3 + t * .55), nN);
  const bookPal = d3.quantize(t => d3.interpolateBlues(.35 + t * .55), nB);
  const allC    = [...narrPal, ...bookPal];

  const W = 860, r0 = 308, r1 = 352;
  const svg = d3.select("#svg-narr")
    .attr("viewBox", `${-W/2} ${-W/2} ${W} ${W}`)
    .attr("width", "100%")
    .style("max-height", "860px");

  const chordL  = d3.chord().padAngle(.009).sortSubgroups(d3.descending)(matrix);
  const arcPath = d3.arc().innerRadius(r0).outerRadius(r1);
  const ribPath = d3.ribbon().radius(r0 - 1);

  let active = null;

  const ribbons = svg.append("g").selectAll("path")
    .data(chordL).join("path")
    .attr("d", ribPath)
    .attr("fill", d => allC[d.source.index])
    .attr("fill-opacity", .48)
    .attr("stroke", d => d3.color(allC[d.source.index]).darker(.6))
    .attr("stroke-width", .4)
    .style("cursor", "pointer")
    .on("mouseover", function(e, d) {
      if (active !== null) return;
      d3.select(this).attr("fill-opacity", .88);
      showTip(
        "<strong>" + labels[d.source.index] + "</strong>" +
        "<span style='color:#aaa'> \u2194 </span>" +
        "<strong>" + labels[d.target.index] + "</strong><br>" +
        "<span class='num'>" + fmt(Math.round(d.source.value)) + "</span> narrations", e);
    })
    .on("mousemove", moveTip)
    .on("mouseout", function() {
      if (active !== null) return;
      d3.select(this).attr("fill-opacity", .48); hideTip();
    });

  function resetAll() {
    active = null;
    ribbons.attr("fill-opacity", .48).attr("display", null);
    arcPaths.attr("fill-opacity", 1);
    hideTip();
  }
  resetFns.narr = resetAll;
  svg.on("click", resetAll);

  const grps = svg.append("g").selectAll("g")
    .data(chordL.groups).join("g")
    .style("cursor", "pointer")
    .on("click", function(e, d) {
      e.stopPropagation();
      if (active === d.index) { resetAll(); return; }
      active = d.index;
      ribbons
        .attr("display", c =>
          (c.source.index === d.index || c.target.index === d.index) ? null : "none")
        .attr("fill-opacity", .82);
      arcPaths.attr("fill-opacity", a => {
        if (a.index === d.index) return 1;
        return chordL.some(c =>
          (c.source.index === d.index && c.target.index === a.index) ||
          (c.target.index === d.index && c.source.index === a.index)) ? 1 : .15;
      });
    })
    .on("mouseover", function(e, d) {
      if (active !== null) return;
      ribbons.attr("fill-opacity", c =>
        (c.source.index === d.index || c.target.index === d.index) ? .88 : .1);
      const isNarr = d.index < nN;
      const total  = matrix[d.index].reduce((s, v) => s + v, 0);
      const top = (isNarr
        ? bookLabels.map((b, j) => ({ label: b, v: narr_book_matrix[d.index][j] || 0 }))
        : narr_keys.map((n, i) => ({ label: n, v: narr_book_matrix[i][d.index - nN] || 0 }))
      ).filter(x => x.v > 0).sort((a, b) => b.v - a.v).slice(0, 5)
       .map(x => x.label + ": <span class='num'>" + fmt(x.v) + "</span>").join("<br>");
      showTip(
        "<strong>" + labels[d.index] + "</strong>" +
        "<span style='color:#777;font-size:.72rem'> " + (isNarr ? "NARRATOR" : "BOOK") + "</span><br>" +
        "<span class='num'>" + fmt(total) + "</span> total narrations<br><br>" +
        "Top links:<br>" + top, e);
    })
    .on("mousemove", moveTip)
    .on("mouseout", function() {
      if (active !== null) return;
      ribbons.attr("fill-opacity", .48); hideTip();
    });

  const arcPaths = grps.append("path")
    .attr("d", arcPath)
    .attr("fill", d => allC[d.index])
    .attr("stroke", d => d3.color(allC[d.index]).darker(.8))
    .attr("stroke-width", .5);

  grps.append("text")
    .each(d => { d.angle = (d.startAngle + d.endAngle) / 2; })
    .attr("transform", d =>
      "rotate(" + (d.angle * 180 / Math.PI - 90) + ")" +
      " translate(" + (r1 + 7) + ")" +
      (d.angle > Math.PI ? " rotate(180)" : ""))
    .attr("text-anchor", d => d.angle > Math.PI ? "end" : "start")
    .attr("fill", d => d.index < nN ? "#c8a0e8" : "#a8ccf0")
    .attr("font-size", d => (d.endAngle - d.startAngle) > .04 ? 10 : 0)
    .attr("font-weight", d => d.index < nN ? "600" : "normal")
    .text(d => labels[d.index].slice(0, 18));

  const legEl = document.getElementById("leg-narr");
  const nh = document.createElement("div");
  nh.style.cssText = "width:100%;font-size:.72rem;color:#c8a0e8;font-weight:700;margin-bottom:3px;padding-left:4px;";
  nh.textContent = "NARRATORS"; legEl.appendChild(nh);
  narr_keys.forEach((k, i) => {
    const div = document.createElement("div");
    div.className = "leg";
    div.innerHTML = "<div class='swatch' style='background:" + narrPal[i] + "'></div>" + k;
    legEl.appendChild(div);
  });
  const bh = document.createElement("div");
  bh.style.cssText = "width:100%;font-size:.72rem;color:#7eb3f0;font-weight:700;margin-top:8px;margin-bottom:3px;padding-left:4px;";
  bh.textContent = "BOOKS"; legEl.appendChild(bh);
  narr_book_keys.forEach((k, i) => {
    const div = document.createElement("div");
    div.className = "leg";
    div.innerHTML = "<div class='swatch' style='background:" + bookPal[i] + "'></div>" + bookLabels[i];
    legEl.appendChild(div);
  });
})();
</script>
</body>
</html>"""

OUT.write_text(html, encoding='utf-8')
sz = OUT.stat().st_size // 1024
print(f"Saved chord.html ({sz} KB)")
