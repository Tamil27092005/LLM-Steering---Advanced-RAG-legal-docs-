---
title: LegalGPT Indian Legal Assistant
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: "5.23.0"
app_file: app.py
pinned: false
license: mit
---

# ⚖️ LegalGPT — Indian Legal Assistant

Multilingual Indian legal assistant supporting **Tamil, Hindi, English, Tanglish, Hinglish, and mixed language queries**.  
Users upload their **own PDF documents** directly — no pre-loaded data directory needed.

## Architecture
```
User uploads PDFs
    ↓  build_index_from_files()  [FAISS HNSW + BM25]
ANY query (Tamil/Hindi/Tanglish/Hinglish/Mixed)
    ↓  translate_to_english()  [Groq LLM + glossary]  ← skipped for English queries
English query
    ↓  retrieve()  [FAISS dense + BM25 sparse RRF]
English chunks
    ↓  generate_answer_en()  [Groq LLM]
    ↓  judge + reflect  [skipped for simple queries — latency optimisation]
English answer
    ↓  translate_answer()  [Groq LLM]
Answer in user's original language
```

## Latency Optimisations
| Optimisation | Saving |
|---|---|
| English queries skip translation LLM call | ~0.4s |
| Simple queries skip judge + self-reflect (2 LLM calls) | ~1–2s |
| FAISS HNSW efSearch reduced (64 vs 256) for small corpora | ~0.2s |
| Translation cache persists within session | ~0.5s per repeated phrase |

## Setup

### 1. Add your API key as a Space Secret
- Go to **Settings → Variables and Secrets**
- Add `GROQ_API_KEY` = your Groq API key

### 2. Deploy
Just deploy the Space — no PDFs needed at deploy time.  
Users upload their own documents through the UI.

## Supported Languages
| Input | Detected As | Example |
|---|---|---|
| Tamil script | ta | இந்திய அரசியலமைப்பில்... |
| Hindi script | hi | भारतीय संविधान में... |
| English | en | What does the Constitution... |
| Tanglish | ta | Arasiyalamaippil pechu sudhandhiram... |
| Hinglish | hi | Samvidhan mein freedom of speech... |
| Mixed | dominant lang | இந்திய Constitution में freedom... |

## Disclaimer
> This tool is for **informational purposes only** and does not constitute legal advice.  
> Always consult a qualified legal professional for legal matters.
