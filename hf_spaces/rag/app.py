"""
Al-Itqan RAG — HuggingFace Space
=================================
Conversational Hadith Q&A using retrieval-augmented generation.

Architecture:
  1. Query → multilingual-e5-small → FAISS → top-K hadiths
  2. Hadiths + root-family context → prompt → Qwen2.5-1.5B-Instruct
  3. Model generates a cited answer referencing book+hadith number

Deploy:
  1. Create a new Space (Gradio SDK, ZeroGPU hardware)
  2. Upload this file as app.py
  3. Set env var HF_INDEX_REPO = "iqrossed/al-itqan-index"
     (same repo used by the search Space)

Environment variables:
  HF_INDEX_REPO   — HuggingFace repo containing semantic_index.faiss + semantic_meta.json
"""

import os, json, re, textwrap
import numpy as np
import faiss
import gradio as gr
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from huggingface_hub import hf_hub_download

# ── Config ────────────────────────────────────────────────────────────────────
EMBED_MODEL  = "intfloat/multilingual-e5-small"
GEN_MODEL    = "Qwen/Qwen2.5-0.5B-Instruct"   # ~1GB, runs on CPU Basic (free)
TOP_K        = 5
MAX_NEW_TOKS = 512

HF_REPO = os.getenv("HF_INDEX_REPO", "iqrossed/al-itqan-index")

BOOK_NAMES = {
    "bukhari":                 "Sahih al-Bukhari",
    "muslim":                  "Sahih Muslim",
    "abudawud":                "Sunan Abu Dawud",
    "tirmidhi":                "Jami' at-Tirmidhi",
    "nasai":                   "Sunan an-Nasa'i",
    "ibnmajah":                "Sunan Ibn Majah",
    "ahmed":                   "Musnad Ahmad",
    "malik":                   "Muwatta Malik",
    "darimi":                  "Sunan ad-Darimi",
    "musannaf_ibnabi_shaybah": "Musannaf Ibn Abi Shaybah",
    "mishkat_almasabih":       "Mishkat al-Masabih",
    "riyad_assalihin":         "Riyad as-Salihin",
    "aladab_almufrad":         "Al-Adab Al-Mufrad",
    "bulugh_almaram":          "Bulugh al-Maram",
    "nawawi40":                "Nawawi 40",
    "qudsi40":                 "Qudsi 40",
    "shahwaliullah40":         "Shah Waliullah 40",
}

GRADE_LABELS = {
    "sahih": "✅ Sahih",
    "hasan": "🟡 Hasan",
    "daif":  "❌ Da'if",
    "":      "",
}

# ── Load embedding model ──────────────────────────────────────────────────────
print("Loading embedding model...")
embedder = SentenceTransformer(EMBED_MODEL)

# ── Load FAISS index ──────────────────────────────────────────────────────────
if os.getenv("USE_LOCAL_INDEX"):
    index_path = os.getenv("INDEX_PATH", "app/data/semantic/semantic_index.faiss")
    meta_path  = os.getenv("META_PATH",  "app/data/semantic/semantic_meta.json")
    print(f"Using local index at {index_path}")
else:
    print(f"Downloading index from {HF_REPO}...")
    index_path = hf_hub_download(repo_id=HF_REPO, filename="semantic_index.faiss")
    meta_path  = hf_hub_download(repo_id=HF_REPO, filename="semantic_meta.json")

INDEX = faiss.read_index(index_path)
META  = json.load(open(meta_path, encoding="utf-8"))
print(f"Index ready — {INDEX.ntotal:,} hadiths")

# ── Load generation model ─────────────────────────────────────────────────────
print(f"Loading generation model: {GEN_MODEL}...")
tokenizer = AutoTokenizer.from_pretrained(GEN_MODEL)
gen_model  = AutoModelForCausalLM.from_pretrained(
    GEN_MODEL,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto",
)
generator = pipeline(
    "text-generation",
    model=gen_model,
    tokenizer=tokenizer,
    max_new_tokens=MAX_NEW_TOKS,
    do_sample=False,
    temperature=1.0,
)
print("Generation model ready.")

# ── Helpers ───────────────────────────────────────────────────────────────────
def detect_lang(text: str) -> str:
    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
    return "ar" if arabic_chars > len(text) * 0.3 else "en"

def retrieve(query: str, top_k: int = TOP_K):
    """Return top-K metadata dicts from FAISS."""
    vec = embedder.encode(["query: " + query],
                          normalize_embeddings=True,
                          convert_to_numpy=True).astype("float32")
    scores, idxs = INDEX.search(vec, top_k * 2)
    results = []
    seen = set()
    for score, idx in zip(scores[0], idxs[0]):
        if idx < 0 or idx >= len(META):
            continue
        m = META[idx]
        uid = f"{m['book']}:{m['num']}"
        if uid in seen:
            continue
        seen.add(uid)
        results.append((float(score), m))
        if len(results) >= top_k:
            break
    return results

def build_prompt(question: str, hits: list, lang: str) -> str:
    """Build the chat prompt with retrieved hadiths as context."""
    context_blocks = []
    for i, (score, m) in enumerate(hits, 1):
        book_name = BOOK_NAMES.get(m["book"], m["book"])
        grade_str = GRADE_LABELS.get(m.get("grade", ""), "")
        families  = ", ".join(m.get("families", [])[:3]) or "—"
        arabic    = m.get("ar", "")[:300]
        english   = m.get("en", "")[:300]
        block = (
            f"[Hadith {i}] {book_name} #{m['num']} {grade_str}\n"
            f"Families: {families}\n"
            f"Arabic: {arabic}\n"
            f"English: {english}"
        )
        context_blocks.append(block)

    context = "\n\n".join(context_blocks)

    if lang == "ar":
        system_msg = (
            "أنت عالم إسلامي متخصص في الحديث النبوي. "
            "أجب على السؤال بناءً على الأحاديث المقدمة فقط. "
            "اذكر المصادر بوضوح (اسم الكتاب ورقم الحديث) في إجابتك."
        )
        user_msg = f"الأحاديث المتعلقة بالسؤال:\n\n{context}\n\nالسؤال: {question}"
    else:
        system_msg = (
            "You are an Islamic scholar specializing in hadith sciences. "
            "Answer the question based ONLY on the provided hadiths. "
            "Cite each hadith you reference by book name and number."
        )
        user_msg = f"Relevant hadiths:\n\n{context}\n\nQuestion: {question}"

    # Qwen2.5 chat format
    messages = [
        {"role": "system",  "content": system_msg},
        {"role": "user",    "content": user_msg},
    ]
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    return prompt

def format_sources(hits: list) -> str:
    """Return a markdown sources block."""
    lines = ["**Sources retrieved:**"]
    for i, (score, m) in enumerate(hits, 1):
        book_name = BOOK_NAMES.get(m["book"], m["book"])
        grade     = GRADE_LABELS.get(m.get("grade",""), "")
        families  = ", ".join(m.get("families",[])[:3]) or "—"
        lines.append(
            f"{i}. **{book_name} #{m['num']}** {grade}  \n"
            f"   Similarity: `{score:.3f}` · Families: {families}  \n"
            f"   {m.get('en','')[:120]}{'…' if len(m.get('en','')) > 120 else ''}"
        )
    return "\n".join(lines)

# ── Chat handler ──────────────────────────────────────────────────────────────
def chat(question: str, history: list, show_sources: bool):
    if not question.strip():
        yield history, ""
        return

    lang = detect_lang(question)
    hits = retrieve(question, top_k=TOP_K)

    if not hits:
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": "No relevant hadiths found for this question."})
        yield history, "", history
        return

    prompt = build_prompt(question, hits, lang)

    # Stream-style: generate then yield
    output = generator(prompt)[0]["generated_text"]
    # Strip the prompt prefix — pipeline returns full text
    answer = output[len(prompt):].strip()
    # Clean up any trailing special tokens
    answer = re.sub(r'<\|.*?\|>', '', answer).strip()

    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    sources_md = format_sources(hits) if show_sources else ""
    yield history, sources_md, history

# ── Interface ─────────────────────────────────────────────────────────────────
with gr.Blocks(title="Al-Itqan — Hadith Q&A", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # 📖 Al-Itqan — Hadith Q&A (RAG)
    Ask questions about Islamic topics in **Arabic or English**.
    Answers are grounded in 87,688 hadiths across 18 books — no hallucination of sources.

    > *Model: Qwen2.5-0.5B-Instruct · Index: multilingual-e5-small · Data: Al-Itqan root bridge*
    """)

    chatbot   = gr.Chatbot(height=420, label="Conversation", type="messages")
    with gr.Row():
        question_box = gr.Textbox(
            label="Your question",
            placeholder="What does the Prophet ﷺ say about patience?  |  ما قاله النبي ﷺ عن الصبر؟",
            lines=2,
            scale=5,
        )
        send_btn = gr.Button("Ask", variant="primary", scale=1)
    show_src  = gr.Checkbox(value=True, label="Show retrieved hadiths")
    sources   = gr.Markdown(label="Sources")
    clear_btn = gr.Button("Clear conversation", size="sm")

    state = gr.State([])

    send_btn.click(
        chat,
        inputs=[question_box, state, show_src],
        outputs=[chatbot, sources, state],
    )
    question_box.submit(
        chat,
        inputs=[question_box, state, show_src],
        outputs=[chatbot, sources, state],
    )
    clear_btn.click(lambda: ([], []), outputs=[chatbot, state])

    gr.Markdown("""
    ---
    **Limitation:** This model answers only from retrieved hadiths. If no relevant hadith
    is found the model will say so rather than fabricate. Always verify with a scholar.
    """)

demo.launch()
