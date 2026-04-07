# Itqan — Architecture & Roadmap
*Last updated: 2026-04-07*

---

## Vision

A unified, offline-capable Islamic study platform that connects the Quran and Hadith through:
- **Root-word navigation** spanning 6,236 Quran ayahs and 87k+ hadiths
- **Thematic study** across 39 scholarly families (each with Quran ayahs + hadiths)
- **Two-layer cross-referencing**: algorithmic (root-bridge) + curated (scholarly HadithReference table)
- **Isnad visualization** (narrator flow across all books, color-coded by grade)
- **Semantic search** ("find content about X" rather than keyword matching)
- **Conversational Q&A** citing actual hadith chains
- **Sunni + Shia coverage** — no other open app does both

**Itqan AI** ([HuggingFace Space](https://huggingface.co/spaces/iqrossed/al-itqan-rag)) is the optional AI companion — concordance search and RAG-powered Q&A over the same corpus.

---

## What's Built

### Core Platform (fully static, offline-capable)

| Component | Entry Point | Status |
|---|---|---|
| **Quran Reader** | `quran/index.html` | ✅ Complete |
| **Hadith Reader** | `app/index.html` | ✅ Complete |
| **Quran→Hadith Bridge** | Click root in Quran → opens Hadith view filtered to that root | ✅ Complete |
| **Thematic Families** | `quran/themes.html` | ✅ Complete |
| **Mushaf View** | `quran/mushaf.html` | ✅ Complete |
| **Chord Diagrams** | `app/chord.html` | ✅ Complete |
| **Concordance Audit** | `app/concordance_audit.html` | ✅ Complete |
| **Isnad Visualizer** | `app/isnad.html` | ✅ Complete |
| **Shia Database** | `app/shia.html` | ✅ Complete (standalone) |
| **Itqan AI** | [HuggingFace Space](https://huggingface.co/spaces/iqrossed/al-itqan-rag) | ✅ Deployed |

### Data Files

| File | Size | Contents | Status |
|---|---|---|---|
| `quran_hadith_bridge.json` | 8.7 MB | 1,651 roots → ayahs + hadith_ids + Lane's + Mufradat | ✅ Built |
| `family_corpus.json` | 2.7 MB | 39 thematic families → Quran+Hadith corpus | ✅ Built |
| `concordance.json` | 16.8 MB | 32,315 words → hadith IDs (inverted index) | ✅ Rebuilt with Musannaf |
| `word_defs_v2.json` | 6.6 MB | 32,315 Arabic words → root, gloss, morph | ⚠ Root gaps (see below) |
| `narrator_index.json` | 0.6 MB | Narrator names → hadith counts, topics, grades | ✅ |
| `hadith_connections.json` | 4.1 MB | Cross-book connections (shared matn, topic, ruling) | ✅ |
| `roots_lexicon.json` | 1.5 MB | 1,651 roots → Lane's Lexicon definitions | ✅ |
| `isnad_graph.json` | — | Narrator nodes + links across 11 books (37,454 parsed chains) | ✅ |
| `search_index.json` | ~60 MB | Full-text search index | ✅ (not in git) |

### Quran Data (`quran/data/`)

| File | Contents |
|---|---|
| `roots_index.json` | 1,651 roots → {ayahs, meaning, family, frequency} |
| `families.json` | 39 thematic families → roots |
| `mufradat.json` | 1,163 classical definitions (Raghib al-Isfahani, d. 1108 CE) |
| `furuq.json` | Semantic distinctions between near-synonym roots |
| `surahs/*.json` | 114 surah files |
| `translations/` | Sahih International English, word-by-word, transliteration |
| `tafsirs/` | Ibn Kathir (Urdu), Bayan ul-Quran — 114 files each |
| `hadith_bridge_summary.json` | Per-root hadith counts for the Connected Hadiths panel |

### Hadith Books (`app/data/sunni/` — 87,057 hadiths)

| Book | Hadiths | Graded | In Concordance |
|---|---|---|---|
| Sahih al-Bukhari | 7,277 | ✅ (self-authenticated) | ✅ |
| Sahih Muslim | 7,368 | ✅ | ✅ |
| Sunan Abu Dawud | 5,276 | ✅ | ✅ |
| Jami' at-Tirmidhi | 4,053 | ✅ | ✅ |
| Sunan an-Nasa'i | 5,685 | ✅ | ✅ |
| Sunan Ibn Majah | 4,079 | ✅ | ✅ |
| Musnad Ahmad | 1,374 | — | ✅ |
| Muwatta Malik | 1,985 | — | ✅ |
| Sunan ad-Darimi | 2,757 | — | ✅ |
| Nawawi 40 + Qudsi 40 + Shah Waliullah 40 | 122 | — | ✅ |
| Riyad as-Salihin | 1,217 | — | ✅ |
| Al-Adab Al-Mufrad | 1,326 | — | ✅ |
| Bulugh al-Maram | 1,767 | — | ✅ |
| Mishkat al-Masabih | 4,427 | — | ✅ |
| Shamail Muhammadiyah | 400 | — | ✅ |
| Musannaf Ibn Abi Shaybah | 37,943 | — | ✅ |

Shia: 18 books, ~15,000+ hadiths — standalone searchable database (separate page, no bridge/family integration)

---

## Confirmed Strategic Decisions

### 1. Two-layer cross-referencing
Not either/or — both layers together:

| Layer | Type | How built | Coverage | Precision |
|---|---|---|---|---|
| **Root bridge** | Algorithmic | `quran_hadith_bridge.json` | All 1,201 shared roots → 384k links | Broad (theme-level) |
| **HadithReference table** | Curated | Manual/editorial, one row per link | Selected ayahs → specific hadiths | Precise (tafsir-level) |

Schema for HadithReference table:
```json
{
  "ayah_key": "2:255",
  "collection": "bukhari",
  "hadith_number": 7439,
  "relationship_type": "tafsir | explanation | ruling | context",
  "note": "optional scholarly note"
}
```
This table lives in `app/data/hadith_references.json`. Start empty; grow over time.

### 2. Shia scope
Shia hadiths remain a standalone searchable database (`app/shia.html`). Not connected to the root bridge, family corpus, or Quran cross-references.

### 3. Embedding language
Embed Arabic text only. English translations are toggleable display, not indexed.

### 4. Musannaf grading
Display as ungraded. No automated grading.

---

## Known Issues

### Issue 1 — Root Form Mismatch in word_defs_v2 ✅ PARTIALLY FIXED
CAMeL Tools canonical root forms differ from Quran roots_index forms for 450 roots.
**Fix applied:** `src/root_alias_map.json` — 131 entries mapping Quran root forms to CAMeL canonical forms. `build_bridge.py` applies this map: +4,977 word→root mappings recovered.

**Still open:** `أمر` (command) and `ولي` (guardianship) have 0 words in word_defs_v2 — CAMeL Tools did not analyze their word forms. Lower priority; statecraft family still gains from the 131 alias fixes.

### Issue 2 — Family Overlap / Noise in Root-Hadith Links ⚠ MEDIUM
Root `خرج` (157 ayahs, 1,964 hadiths) is in `end_of_times` for its apocalyptic meaning, but 95% of its hadiths are about ordinary departure. Family corpus should be **intersection-weighted**: require multiple roots from a family to count a hadith toward it.

### Issue 3 — Embedding Model Choice ✅ RESOLVED
Benchmarked `intfloat/multilingual-e5-small` vs `all-MiniLM-L6-v2` on Arabic hadith queries. e5-small scored **16.4% higher**. Now deployed on the HuggingFace Space with 87k hadith embeddings (216MB FAISS index).

### Issue 4 — HadithReference Table Bootstrap ⚠ LOW
Empty curated cross-reference table at launch. Seed from `ReligiousLLMs/Quran_Hadith_explain_verse_8K` (8k verse-hadith explanation pairs). Verify before publishing.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         ITQAN                                │
│          Static Layer — offline-capable, no backend           │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────────────────┐     │
│  │  QURAN VIEW      │  │  HADITH VIEW                 │     │
│  │  quran/index.html│──│  app/index.html               │     │
│  │  Root panel:     │  │  Browse by book/chapter       │     │
│  │  • Mufradat      │  │  Full-text search             │     │
│  │  • Furuq         │  │  Grade badges                 │     │
│  │  • Families      │  │  Word-level morph defs        │     │
│  │  • Connected     │  │  Root filter (?root=X)        │     │
│  │    hadiths ──────│→ │                               │     │
│  └──────────────────┘  └──────────────────────────────┘     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐    │
│  │ THEMATIC     │  │ CHORD        │  │ ISNAD          │    │
│  │ FAMILIES     │  │ DIAGRAMS     │  │ VISUALIZER     │    │
│  │ 39 families  │  │ D3.js        │  │ D3-Sankey      │    │
│  │ Quran+Hadith │  │ family×book  │  │ 11 books       │    │
│  └──────────────┘  └──────────────┘  └────────────────┘    │
│                                                              │
│  Data: JSON files, lazy loaded, chunked per book            │
└──────────────────────────┬──────────────────────────────────┘
                           │  API calls (graceful degradation)
┌──────────────────────────▼──────────────────────────────────┐
│                    ITQAN AI  (HuggingFace Space)             │
│                                                              │
│  ┌───────────────────────┐  ┌──────────────────────────┐   │
│  │  CONCORDANCE SEARCH   │  │  RAG Q&A                  │   │
│  │  Arabic morphological │  │  Retrieval + generation   │   │
│  │  + English semantic   │  │  Cited answers with isnad │   │
│  │  e5-small embeddings  │  │                           │   │
│  │  FAISS 87k hadiths    │  │                           │   │
│  └───────────────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Principle:** The static layer works fully offline. Itqan AI enhances but is never required.

---

## Future Work

### Hadith→Quran Reverse Bridge
Currently the Quran view links to the Hadith view (`?root=X`). The reverse — opening the Hadith view first and seeing connected Quran verses — is not yet built. The bridge data already supports this; the UI needs implementation.

### Curated HadithReference Table
- Import and verify 8k pairs from `ReligiousLLMs/Quran_Hadith_explain_verse_8K`
- Display gold badges on curated links (vs silver for algorithmic root-bridge links)
- Owner edits `hadith_references.json` directly

### Family Relevance Scoring
Reduce noise in family-hadith links by requiring a hadith to share multiple roots from a family (not just one) before counting it toward that family.

### RAG Model Upgrade
Current: concordance + basic RAG. Future: `Azizkhan22/qwen2.5-7b-hadith-quran-qa-lora` (fine-tuned on Quran+Hadith QA) with root-family-guided retrieval and isnad-preserving citations.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | Vanilla JS + CSS (no framework) | No build step, no server, easiest to audit |
| Styling | CSS variables, dark mode | Already built and tested |
| Arabic fonts | Amiri (body) + Noto Naskh (UI) | Already in use |
| Data format | JSON files, lazy loaded | No server required; chunked per book |
| Isnad viz | D3.js v7 Sankey plugin | MIT license, self-hosted, offline-capable |
| AI hosting | HuggingFace Spaces (Gradio) | Free GPU inference |
| Semantic search | FAISS via HF Space | e5-small embeddings, 87k hadiths |
| Vector storage | FAISS IndexFlatIP | Simple, fast, no database dependency |

---

## HuggingFace Assets

| Asset | License | Integration point |
|---|---|---|
| `meeAtif/hadith_datasets` | MIT | Hadith grading data |
| `ReligiousLLMs/Quran_Hadith_explain_verse_8K` | — | Seed HadithReference table |
| `intfloat/multilingual-e5-small` | MIT | Semantic search embeddings (deployed) |
| `Azizkhan22/qwen2.5-7b-hadith-quran-qa-lora` | Apache-2.0 | Future: Q&A generation |
| `iqrossed/al-itqan-index` | — | FAISS index + concordance (shared dataset) |

---

## Data Flow

```
User clicks root صبر in Quran view
         │
         ▼
[Root panel opens]
  Mufradat definition + Furuq distinctions + family tags
  Connected Quran ayahs (all ayahs with this root)
  Connected hadiths (per-book counts from bridge data)
         │
         ▼
[User clicks a hadith book badge]
  Opens hadith view: app/?root=صبر
  Shows only hadiths containing words from root صبر
  Each word clickable → morphological definition
         │
         ▼
[Optional: Itqan AI]
  Concordance search or natural language Q&A
  Returns cited hadiths with relevance scores
```
