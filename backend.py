# LegalGPT — backend.py

import os, re, time, warnings
import numpy as np
import pdfplumber
from rank_bm25 import BM25Okapi
from openai import OpenAI
from langdetect import detect, DetectorFactory

warnings.filterwarnings("ignore")
DetectorFactory.seed = 42

# ── Groq client ───────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
client       = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

# Valid Groq model names (as of 2025)
CHAT_MODEL        = "openai/gpt-oss-120b"
MAX_CONTEXT_CHARS = 10_000
TOP_K_PAGES       = 6

# ── In-memory store ───────────────────────────────────────────────────────────
_bm25_index  = None
_bm25_corpus = []
_bm25_meta   = []
_trans_cache = {}

# ── Language detection ────────────────────────────────────────────────────────
TAMIL_RE = re.compile(r'[\u0B80-\u0BFF]')
HINDI_RE = re.compile(r'[\u0900-\u097F]')
HINGLISH = {"kya","hai","mein","ka","ki","ke","nahi","hota","saza","kanoon",
            "dhara","nyay","sarkar","adhikar","samvidhan","ipc","crpc","bail"}
TANGLISH = {"iruku","enna","epdi","sattam","neethi","urimai","thandanai",
            "kutram","jaamin","thirumanam","pechu","sudhandhiram"}

def detect_language(text: str) -> str:
    if TAMIL_RE.search(text): return "ta"
    if HINDI_RE.search(text): return "hi"
    words = set(re.findall(r'\b\w+\b', text.lower()))
    if len(words & HINGLISH) >= 2: return "hi"
    if len(words & TANGLISH) >= 1: return "ta"
    try:
        d = detect(text)
        return d if d in ("en","ta","hi") else "en"
    except:
        return "en"

# ── PDF extraction ────────────────────────────────────────────────────────────
def _extract_pages(path: str) -> list:
    pages = []
    try:
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                raw = (page.extract_text(x_tolerance=2, y_tolerance=3) or "").strip()
                if len(raw) < 30:
                    continue
                raw = re.sub(r'\n{3,}', '\n\n', raw)
                raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\xad]', '', raw)
                pages.append({"page": i + 1, "text": raw})
    except Exception as e:
        print(f"⚠️  {path}: {e}")
    return pages

# ── Load documents ────────────────────────────────────────────────────────────
def load_documents(file_paths: list) -> dict:
    global _bm25_index, _bm25_corpus, _bm25_meta
    _bm25_corpus, _bm25_meta = [], []
    _trans_cache.clear()

    total_pages = 0
    file_names  = []

    for path in file_paths:
        fname = os.path.basename(path)
        file_names.append(fname)
        pages = _extract_pages(path)
        for p in pages:
            _bm25_corpus.append(p["text"].lower().split())
            _bm25_meta.append({"doc": fname, "page": p["page"], "text": p["text"]})
        total_pages += len(pages)
        print(f"  ✅ {fname}: {len(pages)} pages")

    if not _bm25_corpus:
        raise ValueError("No text could be extracted from the uploaded files.")

    _bm25_index = BM25Okapi(_bm25_corpus)
    print(f"✅ BM25 ready — {total_pages} pages, {len(file_paths)} file(s)")
    return {"docs": len(file_paths), "pages": total_pages, "files": file_names}

# ── BM25 retrieval ────────────────────────────────────────────────────────────
def _retrieve_context(query: str):
    if _bm25_index is None:
        return "", []

    scores  = _bm25_index.get_scores(query.lower().split())
    top_ids = np.argsort(scores)[::-1][:TOP_K_PAGES]
    top_ids = [i for i in top_ids if scores[i] > 0]

    if not top_ids:
        top_ids = list(range(min(TOP_K_PAGES, len(_bm25_meta))))

    parts, sources, chars = [], [], 0
    for i in top_ids:
        m      = _bm25_meta[i]
        header = f"[{m['doc']} | Page {m['page']}]\n"
        block  = header + m["text"]
        if chars + len(block) > MAX_CONTEXT_CHARS:
            remaining = MAX_CONTEXT_CHARS - chars - len(header)
            if remaining > 200:
                parts.append(header + m["text"][:remaining] + "…")
            break
        parts.append(block)
        sources.append({"doc": m["doc"], "page": m["page"]})
        chars += len(block)

    return "\n\n---\n\n".join(parts), sources

# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM = """\
You are LegalGPT, an expert Indian legal assistant.

Rules:
1. Answer ONLY from the document context provided. No outside knowledge.
2. Cite exact section/article numbers when found in the context.
3. Reply in the SAME language the user asked in (Tamil, Hindi, or English).
4. Use bullet points for lists. Be clear and complete.
5. If the answer is not in the context, say:
   "This information is not available in the uploaded documents."
6. End every answer with:
   "⚠️ This is for informational purposes only and does not constitute legal advice.\""""

# ── Streaming query ───────────────────────────────────────────────────────────
def query_pipeline_stream(question: str):
    """
    Yields (text_chunk, sources, lang, elapsed).
    Text chunks have src=None. Final yield has text_chunk="" and src=list.
    All errors are yielded as text so they always show in the UI.
    """
    t0   = time.time()
    lang = detect_language(question)

    # Check API key first
    if not GROQ_API_KEY or GROQ_API_KEY == "":
        yield "❌ GROQ_API_KEY is not set. Please add it in Space Settings → Secrets.", [], lang, 0
        return

    context, sources = _retrieve_context(question)

    if not context:
        yield "⚠️ No documents loaded. Please upload PDFs first.", [], lang, 0
        return

    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user",   "content":
            f"DOCUMENT CONTEXT:\n{context}\n\nQUESTION: {question}"},
    ]

    try:
        stream = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0,
            max_tokens=1500,
            stream=True,
        )
        got_content = False
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                got_content = True
                yield delta, None, lang, None

        if not got_content:
            yield "⚠️ The model returned an empty response. Please try again.", [], lang, 0
            return

    except Exception as e:
        # Surface the FULL error message so we can debug
        err = str(e)
        print(f"❌ LLM error: {err}")
        yield f"❌ LLM error: {err}", [], lang, 0
        return

    yield "", sources, lang, round(time.time() - t0, 2)