# Unified Islamic Study App — Architecture Plan
*Last updated: 2026-04-05*

---

## Vision

A unified, offline-capable web app that makes deep Islamic study accessible through:
- **Root-word navigation** spanning both the Quran and 102k+ hadiths
- **Thematic study** across 39 scholarly families (each with Quran ayahs + hadiths)
- **Two-layer cross-referencing**: algorithmic (root-bridge) + curated (scholarly HadithReference table)
- **Isnad visualization** (narrator flow across all books, not just Bukhari)
- **Semantic search** ("find content about X" rather than keyword matching)
- **Conversational Q&A** citing actual hadith chains
- **Sunni + Shia coverage** — no other open app does both

The three existing open-source tools (BasilSuhail, HadithRAG, KASHAF) each solve one hard sub-problem. This app is the integration layer that combines them with the root-bridge data none of them have.

---

## Confirmed Strategic Decisions

### 1. Two-layer cross-referencing (agreed)
Not either/or — both layers together:

| Layer | Type | How built | Coverage | Precision |
|---|---|---|---|---|
| **Root bridge** | Algorithmic | `quran_hadith_bridge.json` | All 1,201 shared roots → 384k links | Broad (theme-level) |
| **HadithReference table** | Curated | Manual/editorial, one row per link | Selected ayahs → specific hadiths | Precise (tafsir-level) |

Schema for HadithReference table (mirroring quran.com):
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

### 2. Building blocks, not competitors (agreed)
| Tool | Role | What it contributes |
|---|---|---|
| **KASHAF** | Isnad visualization engine | Sankey/flow diagram renderer (vanilla JS + Google Charts) |
| **BasilSuhail** | Semantic search engine | FAISS index + sentence embeddings pipeline |
| **HadithRAG** | Conversational Q&A | Isnad-preserving vector store schema + retrieval loop |
| **Root bridge** | Cross-corpus linking | The unique layer none of them have |

---

## Data Inventory

### What We Have (D:/Hadith/app/data/)

| File | Size | Contents | Status |
|---|---|---|---|
| `quran_hadith_bridge.json` | 8.7 MB | 1,651 roots → ayahs + hadith_ids + Lane's + Mufradat | ✓ Built |
| `family_corpus.json` | 2.7 MB | 39 thematic families → Quran+Hadith corpus | ✓ Built |
| `concordance.json` | 9.8 MB | 32,315 words → hadith IDs (inverted index) | ⚠ Incomplete (Musannaf missing) |
| `word_defs_v2.json` | 6.6 MB | 32,315 Arabic words → root, gloss, morph | ⚠ Root gaps (see below) |
| `narrator_index.json` | 0.6 MB | Narrator names → hadith counts, topics, grades | ✓ |
| `hadith_connections.json` | 4.1 MB | Cross-book connections (shared matn, topic, ruling) | ✓ |
| `roots_lexicon.json` | 1.5 MB | 1,651 roots → Lane's Lexicon definitions | ✓ |
| `search_index.json` | ~60 MB | Full-text search index | ✓ (not in git) |

### Quran Data (D:/GRAPHS/)

| File | Contents |
|---|---|
| `quran-bil-quran/app/data/roots_index.json` | 1,651 roots → {ayahs, meaning, family, frequency} |
| `quran-bil-quran/app/data/families.json` | 39 thematic families → roots |
| `quran-bil-quran/app/data/mufradat.json` | 1,163 classical definitions (Raghib al-Isfahani) |
| `quran-bil-quran/app/data/matching-ayah.json` | Quran internal cross-references (similar ayahs) |
| `ayah-root.db` | Per-ayah root list (SQLite) |
| `word-root.db` | Root → word locations (SQLite) |
| `ar-tafseer-tahrir-al-tanwir.json` | Full Tahrir al-Tanwir tafsir |
| `tafseer-ibn-e-kaseer-urdu.json` | Ibn Kathir tafsir (Urdu) |

### Hadith Books (D:/Hadith/app/data/sunni/ — 87,057 hadiths)

| Book | Hadiths | Graded | In Concordance |
|---|---|---|---|
| Sahih al-Bukhari | 7,277 | ✓ (self-authenticated) | ✓ |
| Sahih Muslim | 7,368 | ✓ | ✓ |
| Sunan Abu Dawud | 5,276 | ✓ | ✓ |
| Jami' at-Tirmidhi | 4,053 | ✓ | ✓ |
| Sunan an-Nasa'i | 5,685 | ✓ | ✓ |
| Sunan Ibn Majah | 4,079 | ✓ | ✓ |
| Musnad Ahmad | 1,374 | ✗ | ✓ |
| Muwatta Malik | 1,985 | ✗ | ✓ |
| Sunan ad-Darimi | 2,757 | ✗ | ✓ |
| Nawawi 40 + Qudsi 40 + Shah Waliullah 40 | 122 | ✗ | ✓ |
| Riyad as-Salihin | 1,217 | ✗ | ✓ |
| Al-Adab Al-Mufrad | 1,326 | ✗ | ✓ |
| Bulugh al-Maram | 1,767 | ✗ | ✓ |
| Mishkat al-Masabih | 4,427 | ✗ | ✓ |
| Shamail Muhammadiyah | 400 | ✗ | ✓ |
| **Musannaf Ibn Abi Shaybah** | **37,943** | ✗ | **✗ MISSING** |

Shia: 18 books, ~15,000+ hadiths — **standalone searchable database only** (separate page, no bridge/family integration)

---

## Known Issues / Stress Tests

These are confirmed bugs or gaps that must be fixed before building on top of this data.

### Issue 1 — Musannaf Not in Concordance ✓ FIXED (2026-04-05)
**Was:** Zero concordance entries for Musannaf Ibn Abi Shaybah (37,943 hadiths).
**Fix applied:** Re-ran `src/enrich_data.py --step concordance`. Concordance rebuilt: 9.8MB → 16.8MB, 876,430 total entries, **230,599 Musannaf entries** confirmed.

### Issue 2 — Root Form Mismatch in word_defs_v2 ✓ PARTIALLY FIXED (2026-04-05)
**Was:** CAMeL Tools canonical root forms differ from Quran roots_index forms for 450 roots.
**Fix applied:** `src/fix_root_canonicalization.py` built a 129-entry alias map (`src/root_alias_map.json`). Key fixes:
- `قضي` → `قضو` (judgment/judiciary: 80 words recovered)
- `بيع` → `بوع` (pledge/sale: 198 words recovered)
- 127 more defective/hollow verb root aliases auto-detected
- `build_bridge.py` updated to apply alias map: +4,832 word→root mappings, +129 shared roots (1,201 → 1,330)

**Still open:** `أمر` (command) and `ولي` (guardianship) have 0 words in word_defs_v2 — CAMeL Tools did not analyze their word forms. These are Type B gaps requiring a direct hadith text scan. Lower priority; statecraft family still gains from the 129 Type A fixes.

### Issue 3 — Family Overlap / Noise in Root-Hadith Links ⚠ MEDIUM
**Problem:** Root `خرج` (157 ayahs, 1,964 hadiths, meaning "to go out/emerge") is in `end_of_times` family for its apocalyptic meaning, but 95% of its 1,964 hadiths are about ordinary departure, not eschatology.
**Impact:** Showing "1,964 hadiths about End of Times" is misleading. Users searching the End of Times family will get noise.
**Fix:** Family corpus should be **intersection-weighted**: for a hadith to count toward a family, it should share multiple roots from that family, not just one. Implement a relevance score: `family_score = (roots_in_family that appear in this hadith) / (total family roots)`. Set a minimum threshold (e.g., 0.15 = at least 2 roots from a 15-root family).
**Effort:** 2-3 hours pipeline change.

### Issue 4 — Google Charts External Dependency in KASHAF ⚠ LOW
**Problem:** KASHAF's Sankey diagrams depend on `https://www.gstatic.com/charts/loader.js`. If offline or if Google deprecates it, isnad visualization breaks.
**Fix:** Replace with D3.js Sankey (MIT license, self-hosted). D3-sankey is ~5KB additional JS.
**Effort:** 1 day UI work.

### Issue 5 — Embedding Model Choice for Semantic Search ⚠ MEDIUM
**Problem:** BasilSuhail uses `all-MiniLM-L6-v2` (English-first, 384-dim). Hadith Arabic text requires a Classical Arabic model.
**Best available:** `CAMeL-Lab/bert-base-arabic-camelbert-ca` (Apache-2.0) — trained on Classical Arabic including Quran/Hadith-style text. However, it is a BERT encoder, not a sentence-transformer — needs mean-pooling to produce sentence embeddings.
**Alternative:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` — supports Arabic, smaller, easier to deploy, less domain-specific.
**Decision needed:** Run a small benchmark: embed 100 hadith queries, check which model retrieves more relevant results.
**Effort:** 1 day benchmarking.

### Issue 6 — Scale of Semantic Index ⚠ MEDIUM
**Problem:** 87k hadiths × 768 dimensions (camelbert) = ~268MB float32 FAISS index. Too large for a static file served to browsers.
**Fix options:**
  - Host on HuggingFace Space (free GPU inference endpoint) — BasilSuhail's approach scaled up
  - Use a Netlify Function or Cloudflare Worker that proxies a pre-built FAISS index
  - Use quantized int8 embeddings (4× smaller, ~67MB) with minor quality loss
  - Use approximate retrieval over a pre-computed 10k "centroid" index (fast, lossy)
**Decision:** HuggingFace Space for the semantic/Q&A layer; static JSON for root/family layer. Keeps static app fast and offline-capable for the core reading experience.

### Issue 7 — HadithReference Table Bootstrap ⚠ LOW
**Problem:** Starting with an empty curated cross-reference table means the "scholarly tafsir links" feature is empty at launch.
**Fix:** Source initial data from the `ReligiousLLMs/Quran_Hadith_explain_verse_8K` HuggingFace dataset (8k verse-hadith explanation pairs). Use as seed data — manually verify a sample before publishing.
**Effort:** 2-3 hours data import script.

### Issue 8 — Shia Data Scope ✓ RESOLVED
**Decision:** Shia hadiths remain a standalone searchable database (separate page, like current `shia.html`). Not connected to the root bridge, family corpus, or Quran cross-references. No integration with thematic study or isnad visualizer. Just a clean, fast, searchable hadith collection — nothing more.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    STATIC LAYER  (Netlify/GitHub Pages)      │
│  HTML + CSS + Vanilla JS  —  offline-capable PWA             │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  READER     │  │  THEMATIC    │  │  ROOT EXPLORER   │   │
│  │  Quran +    │  │  STUDY       │  │  root → ayahs +  │   │
│  │  Hadith     │  │  39 families │  │  hadiths + defs  │   │
│  │  side-panel │  │  corpus view │  │  Lane's+Mufradat │   │
│  └─────────────┘  └──────────────┘  └──────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ISNAD VISUALIZER  (KASHAF engine, D3 Sankey)        │   │
│  │  All books · narrator color = reliability grade      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Static data served from CDN:                               │
│  quran_hadith_bridge.json (8.7MB, lazy)                     │
│  family_corpus.json (2.7MB, lazy)                           │
│  concordance.json (9.8MB, on-demand)                        │
│  narrator_index.json (0.6MB)                                │
│  Per-book hadith JSON chunks (lazy loaded)                  │
└──────────────────────────┬──────────────────────────────────┘
                           │  API calls (graceful degradation)
┌──────────────────────────▼──────────────────────────────────┐
│            AI LAYER  (HuggingFace Space)                     │
│                                                              │
│  ┌───────────────────────┐  ┌──────────────────────────┐   │
│  │  SEMANTIC SEARCH      │  │  CONVERSATIONAL Q&A       │   │
│  │  (BasilSuhail engine) │  │  (HadithRAG engine)       │   │
│  │  camelbert-ca embeds  │  │  Qwen2.5 LoRA + citations │   │
│  │  FAISS 87k hadiths    │  │  isnad in context         │   │
│  └───────────────────────┘  └──────────────────────────┘   │
│                                                              │
│  Input context from static layer:                           │
│  + root tags  + family tags  + book filter  + grade filter  │
└─────────────────────────────────────────────────────────────┘
```

**Principle:** The static layer works fully offline and without AI. The AI layer enhances but is never required. A user with no internet still gets root navigation, thematic study, isnad diagrams, and the full reader.

---

## Integration Details

### KASHAF → Isnad Visualizer

**Source:** `github.com/OmarShafie/hadith` (Papa Parse, PEG.js, Google Charts Sankey)

**What we take:**
- The Sankey data model: `[source_narrator, target_narrator, hadith_count]` rows
- The narrator color-coding logic: grade → color mapping

**What we replace:**
- Google Charts → D3-sankey (self-hosted, offline-capable)
- Bukhari-only CSV → narrator_index.json across all 17 books
- Static CSV load → dynamic: user selects book, transmission depth, minimum hadith count

**New schema for Sankey input (derived from narrator_index.json):**
```json
{
  "nodes": [{"id": "narrator_name", "grade": "thiqah|da'if|unknown", "hadith_count": 145}],
  "links": [{"source": "A", "target": "B", "value": 23, "books": ["bukhari","muslim"]}]
}
```

**UI:** Sidebar panel in the hadith reader. Click any hadith → "View isnad chain" → Sankey panel opens showing that hadith's transmission tree.

---

### BasilSuhail → Semantic Search

**Source:** `github.com/BasilSuhail/Quran-Hadith-Application-Database` (Flask, SQLite, FAISS, all-MiniLM-L6-v2)

**What we take:**
- The two-corpus unified search concept (Quran + Hadith in one query)
- The FAISS nearest-neighbor retrieval pattern
- The result schema: `{type: "quran"|"hadith", text, reference, score, topic}`

**What we upgrade:**
- 15k hadiths → 87k hadiths (all books)
- `all-MiniLM-L6-v2` → `camelbert-ca` (Classical Arabic domain)
- Flask → HuggingFace Spaces (Gradio, free hosting)
- No root context → **every result tagged with root family** from bridge

**Pre-computation pipeline** (`src/build_semantic_index.py`):
1. For each hadith, embed Arabic text with camelbert-ca (mean-pool CLS)
2. For each Quran ayah, embed Arabic text the same way
3. Build FAISS IndexFlatIP (inner product = cosine similarity on normalized vecs)
4. Save: `semantic_index.faiss` + `semantic_meta.json` (id→reference mapping)
5. Deploy on HuggingFace Space as Gradio app with public API

**API contract (called from static frontend):**
```
GET /search?q=مكارم+الأخلاق&limit=10&filter_family=knowledge&filter_grade=sahih
→ [{type, text, reference, score, family, grade}, ...]
```

---

### HadithRAG → Conversational Q&A

**Source:** `github.com/Quchluk/HadithRAG` (Python, ChromaDB, full isnad in metadata)

**What we take:**
- **Isnad-preserving schema**: storing full chain text in vector metadata, not just hadith text. This is what makes answers citable.
- Retrieval-then-generate loop
- Context window management for multi-hadith answers

**What we upgrade:**
- ChromaDB → FAISS (same index as semantic search, avoids dual infrastructure)
- Generic LLM → `Azizkhan22/qwen2.5-7b-hadith-quran-qa-lora` (fine-tuned on Quran+Hadith QA, specifically trained to reduce hallucination)
- No root context → **question is first converted to roots** using the bridge, then retrieval is guided by root family

**System prompt injection from bridge:**
```
User asks: "What did the Prophet say about forgiveness?"
→ detect roots: غفر، عفو، رحم
→ inject: "Search primarily within family: mercy (الرحمة والمغفرة)"
→ retrieve top-15 hadiths from mercy family
→ generate answer citing full isnad
```

**UI:** "Ask" button in sidebar. Response includes: answer text + 3-5 cited hadiths with full isnad + "View in reader" deep links.

---

### Root Bridge → Cross-Reference Layer (Unique to this app)

**Files:** `quran_hadith_bridge.json` + `family_corpus.json`

**UI patterns:**
1. Click any Arabic word in Quran reader → root popup → "X hadiths on this root" → opens hadith panel
2. Click any Arabic word in Hadith reader → root popup → "X Quran ayahs on this root" → opens Quran panel
3. Thematic Study page: pick family → grid of ayahs + hadiths organized by root sub-theme
4. Root Explorer: search/browse roots alphabetically → full cross-corpus view

**HadithReference table** (curated layer on top):
- Displayed as "direct tafsir links" (gold badge) vs root-bridge links (silver badge)
- Seeded from `ReligiousLLMs/Quran_Hadith_explain_verse_8K` (8k pairs, verify before publishing)
- Users/scholars can submit new links through a GitHub PR workflow

---

## Build Phases

### Phase 0 — Fix Data Before Building (Week 1)
Do not build any UI on top of broken data.

- [ ] **Fix Issue 1**: Rebuild concordance including Musannaf (run enrich_data.py)
- [ ] **Fix Issue 2**: Root canonicalization pass — recover أمر, ولي, بيع, قضي words from concordance
- [ ] **Fix Issue 3**: Implement family relevance scoring (multi-root threshold)
- [ ] Rebuild `quran_hadith_bridge.json` and `family_corpus.json` with all fixes applied
- [ ] Verify Musannaf is now in concordance and bridge
- [ ] Run bridge_analysis.json again; confirm statecraft family gains hadiths

### Phase 1 — Static App Core (Week 2-3)
No AI, no embedding, no external APIs. Everything works offline.

- [ ] Project scaffold: new repo, Netlify config, folder structure
- [ ] Reader: Quran + Hadith side-by-side (reuse quran-bil-quran + hadith app patterns)
- [ ] Root Explorer: click word → root panel → Quran ayahs + hadiths + Lane's + Mufradat
- [ ] Thematic Study page: 39-family grid → family detail page
- [ ] HadithReference table: stub file, display gold badge on linked ayahs/hadiths
- [ ] PWA: service worker, manifest, offline caching strategy for core data files

### Phase 2 — Isnad Visualizer (Week 4)
Port KASHAF with D3 Sankey.

- [ ] Build `narrator_network.json` from narrator_index.json (nodes + links)
- [ ] Implement D3-sankey panel component (replace Google Charts)
- [ ] Grade → color mapping (thiqah=green, hasan=yellow, da'if=red, unknown=grey)
- [ ] Filter controls: by book, by transmission depth, by minimum count
- [ ] Click narrator → mini-bio panel (from narrator_index data)

### Phase 3 — Semantic Search (Week 5-6)
BasilSuhail engine, scaled and upgraded.

- [ ] Benchmark camelbert-ca vs multilingual-MiniLM on 100 hadith queries
- [ ] Build `src/build_semantic_index.py` pipeline
- [ ] Run embedding on all 87k hadiths + 6,236 ayahs
- [ ] Deploy HuggingFace Space (Gradio) with FAISS index
- [ ] Wire frontend search bar to Space API (graceful degradation if offline)
- [ ] Tag search results with root family from bridge

### Phase 4 — Conversational Q&A (Week 7-8)
HadithRAG engine, deployed.

- [ ] Adapt HadithRAG schema to use isnad-preserving metadata
- [ ] Integrate Qwen2.5 LoRA model for answer generation
- [ ] Build question→roots→family→retrieval pipeline
- [ ] Build "Ask" sidebar UI with deep-link citations
- [ ] Rate limiting, abuse prevention on the HuggingFace Space

### Phase 5 — Curated HadithReference Table (Ongoing)
- [ ] Import and verify 8k pairs from ReligiousLLMs/Quran_Hadith_explain_verse_8K
- [ ] Build submission workflow (GitHub PR template)
- [ ] Display gold badges on curated links throughout the reader

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | Vanilla JS + CSS (no framework) | Matches existing quran-bil-quran + hadith app; no build step; easiest to audit |
| Styling | CSS variables, dark mode (existing system) | Already built and tested |
| Arabic fonts | Amiri (body) + Noto Naskh (UI) | Already in use |
| Static hosting | Netlify | Already configured, free, CDN |
| Data format | JSON files, lazy loaded | No server required; chunked per book |
| Isnad viz | D3.js v7 Sankey plugin | MIT license, self-hosted, offline-capable |
| AI hosting | HuggingFace Spaces (Gradio) | Free GPU inference; Arabic community active there |
| Semantic search | FAISS (Python build) → served via HF Space | Proven at scale by BasilSuhail + HadithRAG |
| Embedding model | camelbert-ca (Apache-2.0) | Classical Arabic domain match; best open license |
| Q&A model | Qwen2.5-7B + hadith LoRA (Apache-2.0) | Fine-tuned for this exact task; hallucination-reduced |
| Vector storage | FAISS IndexFlatIP | Simple, fast, no database dependency |
| PWA | Service Worker + Cache API | Allows full offline use of static layer |

---

## Data Flow Summary

```
User types query: "ما قاله النبي عن الصبر"
         │
         ▼
[1. Root extraction]
  word_defs_v2.json → roots: {صبر, قول}
         │
         ▼
[2. Family lookup]
  family_corpus.json → families: {patience_gratitude, speech_communication}
         │
         ├─── [3a. Static: Root bridge results]
         │    quran_hadith_bridge.json[صبر].hadith_ids → list of hadith IDs
         │    Render in reader immediately (no network needed)
         │
         └─── [3b. AI: Semantic + Q&A] (if online)
              POST /search?roots=صبر&family=patience_gratitude
              → FAISS top-20 hadiths
              → Qwen2.5 generates cited answer
              → Display in sidebar with isnad
```

---

## HuggingFace Assets to Integrate

| Asset | License | Integration point |
|---|---|---|
| `meeAtif/hadith_datasets` | MIT | Already in use (grading) |
| `ReligiousLLMs/Quran_Hadith_explain_verse_8K` | — | Seed HadithReference table |
| `CAMeL-Lab/bert-base-arabic-camelbert-ca` | Apache-2.0 | Semantic search embeddings |
| `Azizkhan22/qwen2.5-7b-hadith-quran-qa-lora` | Apache-2.0 | Q&A generation |
| `Abdo1Kamr/Arabic_Hadith` | — | Cross-check diacritized Arabic text |
| `rwmasood/hadith-qa-pair` | CC-BY-4.0 | Fine-tuning evaluation / test set |
| `islamicmmlu/leaderboard` | — | Benchmark our Q&A quality |

---

## Open Questions (Decisions Pending)

1. **App name**: See name candidates section below — pending decision.
2. **Shia integration**: ✓ Resolved — stays as a standalone searchable database (separate page). No connection to root bridge, families, or Quran cross-references.
3. **HadithReference table governance**: ✓ Resolved — owner edits `hadith_references.json` directly. No PR workflow. Seed from `ReligiousLLMs/Quran_Hadith_explain_verse_8K`, verify manually before publishing.
4. **Embedding language**: ✓ Resolved — embed Arabic text only. English translations are toggleable display, not indexed.
5. **Musannaf grading**: ✓ Resolved — display as ungraded. No automated grading.
6. **Isnad depth**: ✓ Resolved — build it. Musannaf data already has full chains in English as "A → B → C → D → E" in the narrator field. Other books have first narrator only (Bukhari: "Narrated X", Muslim: "On authority of X"). Phase 2: use Musannaf's full chains for the Sankey. Phase 3: NLP parse Arabic isnad text for remaining books.

## App Name Candidates

| Name | Arabic | Meaning | Resonance |
|---|---|---|---|
| **Al-Jami'** | الجامع | The Comprehensive Collector | Direct echo of classical hadith collections: Jami' al-Tirmidhi, Jami' al-Bukhari. Scholars name comprehensive compilations "jami'". |
| **Mizan** | الميزان | The Scale / The Balance | Weighing hadith evidence, balancing Quran with Sunnah. "Wa wada'a al-mizan" (55:7). Ibn Hajar's rijal critique work is Mizan al-I'tidal. |
| **Manar** | المنار | The Lighthouse / The Beacon | Guidance through Islamic knowledge. Classical journal of Islamic scholarship (Al-Manar, Rashid Rida). Clean, one word, memorable. |
| **Rawda** | الروضة | The Garden | Classical Islamic books titled "Rawdat X" (Rawdat al-Talibin, Rawdat al-Muhaddithin). Beautiful imagery — a garden of hadith. |
