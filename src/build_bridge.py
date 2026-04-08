"""
build_bridge.py — Quran ↔ Hadith Knowledge Bridge

Reads:
  quran/data/roots_index.json        — Quran root → {ayahs, meaning, family}
  quran/data/families.json           — 39 thematic families → roots
  quran/data/mufradat.json           — classical lexicon (Raghib al-Isfahani)
  app/data/word_defs_v2.json         — Hadith word → root
  app/data/concordance.json          — Hadith word → [book:id, ...]
  app/data/roots_lexicon.json        — roots → Lane's Lexicon

Outputs:
  app/data/quran_hadith_bridge.json  — root → {ayahs, hadith_ids, families, stats}
  app/data/family_corpus.json        — family → {roots, ayahs, hadiths, book_breakdown}
  src/bridge_analysis.json           — cross-correlation analysis & statistics
"""

import json
import os
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
GRAPHS = str(ROOT / "quran" / "data")
HADITH = str(ROOT / "app" / "data")
OUT = str(ROOT / "app" / "data")
ANALYSIS_OUT = str(ROOT / "src")

def load(path):
    print(f"  Loading {os.path.basename(path)}...")
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save(path, data, indent=None):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    size_kb = os.path.getsize(path) / 1024
    print(f"  Saved {os.path.basename(path)} ({size_kb:.0f} KB)")

def book_of(hadith_id):
    """Extract book name from 'bukhari:ch:id' or legacy 'bukhari:id' style ID."""
    return hadith_id.split(":")[0] if ":" in hadith_id else "unknown"

# ─── Load all sources ────────────────────────────────────────────────────────

print("Loading sources...")
q_roots   = load(f"{GRAPHS}/roots_index.json")     # root → {b, m, f, v, fam}
families  = load(f"{GRAPHS}/families.json")         # family → {name_ar, meaning, roots[]}
mufradat  = load(f"{GRAPHS}/mufradat.json")         # root → {r, t}
word_defs = load(f"{HADITH}/word_defs_v2.json")     # word → {r, g, ...}
conc      = load(f"{HADITH}/concordance.json")      # word → [book:id, ...]
roots_lex = load(f"{HADITH}/roots_lexicon.json")    # root → {definition_en}

# Root alias map: roots_index form → word_defs_v2 canonical form
# Fixes CAMeL Tools canonicalization differences (قضي→قضو, بيع→بوع, etc.)
alias_map_path = os.path.join(os.path.dirname(__file__), "root_alias_map.json")
alias_map = {}
if os.path.exists(alias_map_path):
    alias_map = load(alias_map_path)
    print(f"  Root alias map: {len(alias_map)} entries")

print(f"  Quran roots: {len(q_roots)}")
print(f"  Families: {len(families)}")
print(f"  Hadith words: {len(word_defs)}")
print(f"  Concordance entries: {len(conc)}")

# ─── Build root → words → hadiths map ────────────────────────────────────────

print("\nBuilding root→words index from Hadith vocabulary...")
root_to_words = defaultdict(list)
for word, info in word_defs.items():
    if isinstance(info, dict) and "r" in info:
        root_to_words[info["r"]].append(word)

print(f"  Unique hadith roots (word_defs_v2): {len(root_to_words)}")

# Extend: for each alias قضي→قضو, make root_to_words['قضي'] also include قضو words
alias_extensions = 0
for qr_root, wd_root in alias_map.items():
    if qr_root != wd_root and wd_root in root_to_words:
        # Merge wd_root words into qr_root entry (avoid duplicates)
        existing = set(root_to_words[qr_root])
        additions = [w for w in root_to_words[wd_root] if w not in existing]
        root_to_words[qr_root].extend(additions)
        alias_extensions += len(additions)

print(f"  After alias expansion: {alias_extensions} additional word→root mappings applied")

# ─── Build family → roots map ────────────────────────────────────────────────

print("\nBuilding family→roots index...")
# families.json: family_key → {name_ar, meaning, roots: [Arabic roots]}
family_root_map = {}  # family_key → set of roots
for fam_key, fam_data in families.items():
    family_root_map[fam_key] = set(fam_data.get("roots", []))

# Also build reverse: root → [family_keys]
root_to_families = defaultdict(list)
for fam_key, root_set in family_root_map.items():
    for root in root_set:
        root_to_families[root].append(fam_key)

# ─── Build quran_hadith_bridge.json ──────────────────────────────────────────

print("\nBuilding Quran↔Hadith root bridge...")
bridge = {}
shared_roots = 0
total_hadith_connections = 0

for root, qdata in q_roots.items():
    words_in_hadith = root_to_words.get(root, [])

    # Collect all hadith IDs reachable via this root's words
    hadith_id_set = set()
    for word in words_in_hadith:
        hadith_id_set.update(conc.get(word, []))

    # Book breakdown
    book_counts = defaultdict(int)
    for hid in hadith_id_set:
        book_counts[book_of(hid)] += 1

    # Families this root belongs to (from Quran families.json)
    root_families = root_to_families.get(root, [])
    # Also use the 'fam' field from roots_index itself
    if "fam" in qdata and qdata["fam"] and qdata["fam"] not in root_families:
        root_families = [qdata["fam"]] + root_families

    # Definitions
    definitions = {}
    if root in mufradat:
        definitions["mufradat"] = mufradat[root].get("t", "")[:500]
    if root in roots_lex:
        definitions["lanes"] = roots_lex[root].get("definition_en", "")[:500]
    definitions["quran_meaning"] = qdata.get("m", "")

    bridge[root] = {
        "ayahs": qdata.get("v", []),
        "ayah_count": len(qdata.get("v", [])),
        "hadith_ids": sorted(hadith_id_set),
        "hadith_count": len(hadith_id_set),
        "words_in_hadith": words_in_hadith,
        "families": root_families,
        "book_breakdown": dict(book_counts),
        "definitions": definitions,
        "frequency_quran": qdata.get("f", 0),
    }

    if hadith_id_set:
        shared_roots += 1
        total_hadith_connections += len(hadith_id_set)

print(f"  Roots with Quran data: {len(bridge)}")
print(f"  Roots with Hadith connections: {shared_roots}")
print(f"  Total Quran↔Hadith links: {total_hadith_connections:,}")

# ─── Build family_corpus.json ─────────────────────────────────────────────────

print("\nBuilding 39-family thematic corpus...")
family_corpus = {}

for fam_key, fam_data in families.items():
    fam_roots = fam_data.get("roots", [])
    all_ayahs = []
    all_hadith_ids = set()
    book_counts = defaultdict(int)
    root_stats = []

    for root in fam_roots:
        if root in bridge:
            b = bridge[root]
            all_ayahs.extend(b["ayahs"])
            all_hadith_ids.update(b["hadith_ids"])
            for book, cnt in b["book_breakdown"].items():
                book_counts[book] += cnt
            root_stats.append({
                "root": root,
                "ayah_count": b["ayah_count"],
                "hadith_count": b["hadith_count"],
                "frequency_quran": b["frequency_quran"],
            })

    # Sort roots by total Hadith coverage
    root_stats.sort(key=lambda x: x["hadith_count"], reverse=True)

    family_corpus[fam_key] = {
        "name_ar": fam_data.get("name_ar", ""),
        "meaning": fam_data.get("meaning", ""),
        "roots": fam_roots,
        "root_count": len(fam_roots),
        "ayahs": sorted(set(all_ayahs)),
        "ayah_count": len(set(all_ayahs)),
        "hadith_ids": sorted(all_hadith_ids),
        "hadith_count": len(all_hadith_ids),
        "book_breakdown": dict(sorted(book_counts.items(), key=lambda x: -x[1])),
        "root_stats": root_stats,
    }

print(f"  Families built: {len(family_corpus)}")
for fk, fc in sorted(family_corpus.items(), key=lambda x: -x[1]["hadith_count"])[:10]:
    print(f"    {fk:25s}: {fc['ayah_count']:4d} ayahs, {fc['hadith_count']:6d} hadiths, {fc['root_count']} roots")

# ─── Cross-correlation analysis ────────────────────────────────────────────────

print("\nRunning cross-correlation analysis...")

# 1. All books present
all_books = set()
for root, bdata in bridge.items():
    all_books.update(bdata["book_breakdown"].keys())
all_books = sorted(all_books)

# 2. Per-book family breakdown (how much each book covers each theme)
book_family_matrix = {}  # book → family → hadith_count
for book in all_books:
    book_family_matrix[book] = {}
    for fk, fc in family_corpus.items():
        count = fc["book_breakdown"].get(book, 0)
        book_family_matrix[book][fk] = count

# 3. Root frequency comparison: Quran rank vs Hadith rank
root_quran_freq = [(r, d["frequency_quran"]) for r, d in bridge.items()]
root_quran_freq.sort(key=lambda x: -x[1])
root_hadith_freq = [(r, d["hadith_count"]) for r, d in bridge.items()]
root_hadith_freq.sort(key=lambda x: -x[1])

quran_rank = {r: i+1 for i, (r, _) in enumerate(root_quran_freq)}
hadith_rank = {r: i+1 for i, (r, _) in enumerate(root_hadith_freq)}

# Roots over-represented in Hadith vs Quran (rank much higher in Hadith)
rank_delta = []
for root in bridge:
    qr = quran_rank.get(root, 9999)
    hr = hadith_rank.get(root, 9999)
    if bridge[root]["hadith_count"] > 100:  # meaningful presence
        rank_delta.append({
            "root": root,
            "quran_rank": qr,
            "hadith_rank": hr,
            "delta": qr - hr,  # positive = more prominent in Hadith than Quran
            "quran_freq": bridge[root]["frequency_quran"],
            "hadith_count": bridge[root]["hadith_count"],
            "meaning": bridge[root]["definitions"].get("quran_meaning", "")[:120],
        })

rank_delta.sort(key=lambda x: -x["delta"])
over_in_hadith = rank_delta[:20]   # most over-represented in Hadith
over_in_quran  = sorted(rank_delta, key=lambda x: x["delta"])[:20]  # most under

# 4. Ayah coverage: which ayahs are connected to the most hadiths?
ayah_hadith_count = defaultdict(int)
for root, bdata in bridge.items():
    for ayah in bdata["ayahs"]:
        ayah_hadith_count[ayah] += bdata["hadith_count"]

top_ayahs = sorted(ayah_hadith_count.items(), key=lambda x: -x[1])[:50]

# 5. Summary stats
analysis = {
    "summary": {
        "quran_total_roots": len(q_roots),
        "hadith_total_roots": len(root_to_words),
        "shared_roots": shared_roots,
        "overlap_pct": round(shared_roots / len(q_roots) * 100, 1),
        "total_quran_ayahs": sum(d["ayah_count"] for d in bridge.values()),
        "total_hadith_ids_reachable": total_hadith_connections,
        "thematic_families": len(families),
        "all_books": all_books,
    },
    "family_summary": {
        fk: {
            "name_ar": fc["name_ar"],
            "ayah_count": fc["ayah_count"],
            "hadith_count": fc["hadith_count"],
            "root_count": fc["root_count"],
        }
        for fk, fc in sorted(family_corpus.items(), key=lambda x: -x[1]["hadith_count"])
    },
    "book_family_matrix": book_family_matrix,
    "root_frequency_comparison": {
        "top_quran_roots": [{"root": r, "freq": f, "hadith_count": bridge[r]["hadith_count"]}
                            for r, f in root_quran_freq[:30]],
        "top_hadith_roots": [{"root": r, "hadith_count": c, "quran_freq": bridge[r]["frequency_quran"]}
                             for r, c in root_hadith_freq[:30]],
        "over_represented_in_hadith": over_in_hadith,
        "over_represented_in_quran": over_in_quran,
    },
    "top_ayahs_by_hadith_connection": [
        {"ayah": a, "connected_hadiths": c} for a, c in top_ayahs
    ],
}

# ─── Save outputs ─────────────────────────────────────────────────────────────

print("\nSaving outputs...")
save(f"{OUT}/quran_hadith_bridge.json", bridge)
save(f"{OUT}/family_corpus.json", family_corpus)
save(f"{ANALYSIS_OUT}/bridge_analysis.json", analysis, indent=2)

print("\n✓ Done. Summary:")
print(f"  • {shared_roots} shared roots link {len(q_roots)} Quran roots ↔ Hadith")
print(f"  • {total_hadith_connections:,} total Quran↔Hadith root connections")
print(f"  • 39 thematic families with full Quran+Hadith coverage")
print(f"  • Top family by hadiths: {max(family_corpus.items(), key=lambda x: x[1]['hadith_count'])[0]}")
