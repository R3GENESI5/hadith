---
title: Al-Itqan Hadith Q&A
emoji: 📖
colorFrom: green
colorTo: blue
sdk: gradio
sdk_version: "5.23.3"
app_file: app.py
pinned: false
license: apache-2.0
---

# Al-Itqan — Hadith Q&A (RAG)

Ask questions about Islamic topics in Arabic or English.
Answers are grounded in 87,688 hadiths — sources always cited, no hallucination.

## How it works

1. Your question is encoded with `intfloat/multilingual-e5-small`
2. FAISS retrieves the 5 most semantically relevant hadiths
3. `Qwen2.5-1.5B-Instruct` generates a cited answer from those hadiths only

## Setup

1. Run `src/build_semantic_index.py` from the Al-Itqan repo
2. Upload `app/data/semantic/` to a HuggingFace dataset repo
3. Set `HF_INDEX_REPO` environment variable in Space settings
4. Hardware: CPU Basic (free tier) — model fits in ~1GB RAM

## Models

| Role | Model | License |
|------|-------|---------|
| Embeddings | `intfloat/multilingual-e5-small` | Apache-2.0 |
| Generation | `Qwen/Qwen2.5-0.5B-Instruct` | Apache-2.0 |

## Limitation

The model answers **only** from retrieved hadiths. If no relevant hadith is found
it will say so rather than fabricate. Always verify rulings with a qualified scholar.

## Data

Part of the [Al-Itqan](https://github.com/your-org/al-itqan) project —
87,688 hadiths with Quran root-morphology bridge and 39 thematic families.
