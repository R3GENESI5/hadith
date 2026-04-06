---
title: Al-Itqan Semantic Hadith Search
emoji: 🔍
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: "5.23.3"
app_file: app.py
pinned: false
license: apache-2.0
---

# Al-Itqan — Semantic Hadith Search

Search **87,688 hadiths** across 18 books by *meaning*, not just keywords.
Supports Arabic and English queries using multilingual embeddings.

## Features

- Arabic + English query support (auto-detected)
- Filter by book, thematic family, or grade (Sahih/Hasan)
- Results include Arabic text, English translation, grade, and Quran family tags
- ~300ms search latency on CPU

## Setup

1. Run `src/build_semantic_index.py` from the Al-Itqan repo to generate the FAISS index
2. Upload `app/data/semantic/` to a HuggingFace dataset repo
3. Set the `HF_INDEX_REPO` environment variable to that repo ID in Space settings

## Model

`intfloat/multilingual-e5-small` — Apache-2.0, 117MB, 100-language support including Classical Arabic.

## Data

Part of the [Al-Itqan](https://github.com/your-org/al-itqan) project —
87,688 hadiths with Quran root-morphology bridge and 39 thematic families.
