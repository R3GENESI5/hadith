"""
rebuild_bridge_ids.py — Regenerate per-root bridge_ids/*.json with chapter-aware IDs.

The old format stored {book: [idInBook, ...]} which was AMBIGUOUS because
idInBook restarts at 1 for every chapter. This caused false matches when
filtering hadiths by root — e.g., every hadith #2 in ALL chapters matched.

New format: {book: {chapter_idx: [idInBook, ...]}}
Example:    {"bukhari": {"56": [259, 260], "64": [278, 349]}}

This script scans all hadith Arabic text directly, matching against words
known to belong to each Quran root (from word_defs_v2.json), and writes
one JSON file per root to app/data/bridge_ids/.

Usage:
    python src/rebuild_bridge_ids.py
"""

import json, os, re, glob, shutil
from pathlib import Path
from collections import defaultdict

ROOT    = Path(__file__).resolve().parent.parent
DATA    = ROOT / "app" / "data"
OUT_DIR = DATA / "bridge_ids"

# ── Arabic helpers ───────────────────────────────────────────────────────────

TASHKEEL = re.compile(
    r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]')

def strip_tashkeel(s):
    return TASHKEEL.sub('', s)

def tokenize(text):
    """Split Arabic text into bare (no-diacritics) tokens."""
    stripped = strip_tashkeel(text)
    return set(stripped.split())

# ── Load word_defs_v2 → root→words mapping ──────────────────────────────────

print("Loading word_defs_v2.json...")
word_defs = json.load(open(DATA / "word_defs_v2.json", encoding="utf-8"))

root_to_words = defaultdict(set)
for word, info in word_defs.items():
    if isinstance(info, dict) and "r" in info:
        root_to_words[info["r"]].add(word)

print(f"  {len(root_to_words)} unique roots, {len(word_defs)} words")

# ── Load Quran roots_index to know WHICH roots to bridge ────────────────────

print("Loading Quran roots_index.json...")
q_roots = json.load(open(ROOT / "quran" / "data" / "roots_index.json", encoding="utf-8"))
print(f"  {len(q_roots)} Quran roots")

# Only bridge roots that appear in both Quran and Hadith
bridge_roots = {r for r in q_roots if r in root_to_words}
print(f"  {len(bridge_roots)} shared roots to bridge")

# ── Scan all hadiths and build root → {book: {ch: [ids]}} ──────────────────

print("\nScanning all hadiths...")

# Pre-build: word → set of roots (for fast lookup during scan)
word_to_roots = defaultdict(set)
for root in bridge_roots:
    for word in root_to_words[root]:
        word_to_roots[word].add(root)

print(f"  {len(word_to_roots)} indexed words across {len(bridge_roots)} roots")

# root → {book: {ch_idx: set(idInBook)}}
bridge = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))

sunni_dir = DATA / "sunni"
total_hadiths = 0
matched_hadiths = 0

for book_dir in sorted(sunni_dir.iterdir()):
    if not book_dir.is_dir():
        continue
    idx_path = book_dir / "index.json"
    if not idx_path.exists():
        continue
    book_id = book_dir.name
    chapters = json.load(open(idx_path, encoding="utf-8"))

    for ch_idx, ch in enumerate(chapters):
        ch_file = book_dir / ch["file"]
        if not ch_file.exists():
            continue
        hadiths = json.load(open(ch_file, encoding="utf-8"))
        for h in hadiths:
            total_hadiths += 1
            arabic = h.get("arabic", "")
            if not arabic:
                continue
            iib = h.get("idInBook") or h.get("id_in_book")
            if iib is None:
                continue

            tokens = tokenize(arabic)
            matched_roots = set()
            for tok in tokens:
                if tok in word_to_roots:
                    matched_roots.update(word_to_roots[tok])

            if matched_roots:
                matched_hadiths += 1
                for root in matched_roots:
                    bridge[root][book_id][ch_idx].add(iib)

print(f"  Scanned {total_hadiths:,} hadiths, {matched_hadiths:,} matched at least one root")

# ── Write bridge_ids/*.json ─────────────────────────────────────────────────

print(f"\nWriting {len(bridge)} bridge files to {OUT_DIR}/...")

# Clear old files
if OUT_DIR.exists():
    shutil.rmtree(OUT_DIR)
OUT_DIR.mkdir(parents=True, exist_ok=True)

total_connections = 0
for root in sorted(bridge.keys()):
    books = bridge[root]
    out = {}
    for book_id in sorted(books.keys()):
        chapters = books[book_id]
        out[book_id] = {}
        for ch_idx in sorted(chapters.keys()):
            ids = sorted(chapters[ch_idx])
            out[book_id][str(ch_idx)] = ids
            total_connections += len(ids)

    with open(OUT_DIR / f"{root}.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

print(f"  Wrote {len(bridge)} root files")
print(f"  Total connections: {total_connections:,}")

# ── Also regenerate hadith_bridge_summary.json (used by Quran app) ──────────

print("\nBuilding hadith_bridge_summary.json...")
summary = {}
for root in bridge:
    book_counts = {}
    total = 0
    for book_id, chapters in bridge[root].items():
        count = sum(len(ids) for ids in chapters.values())
        book_counts[book_id] = count
        total += count
    summary[root] = {"n": total, "b": book_counts}

summary_path = ROOT / "quran" / "hadith-data" / "hadith_bridge_summary.json"
if summary_path.parent.exists():
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  Saved hadith_bridge_summary.json ({len(summary)} roots)")
else:
    print(f"  Skipped hadith_bridge_summary.json (directory not found)")

print("\n✓ Done!")
