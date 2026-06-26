"""
LegalGPT — Gradio 5.x
"""

import gradio as gr
from backend import load_documents, query_pipeline_stream, _trans_cache

_index_ready = False
LANG_FLAGS   = {"ta": "🇮🇳 Tamil", "hi": "🇮🇳 Hindi", "en": "🇬🇧 English"}

def _fmt_sources(sources):
    if not sources:
        return ""
    seen, lines = set(), ["**📚 Sources**"]
    for s in sources:
        k = f"{s['doc']}:{s['page']}"
        if k not in seen:
            seen.add(k)
            lines.append(f"- `{s['doc']}` — page {s['page']}")
    return "\n".join(lines)

def _msg(role, content):
    return {"role": role, "content": content}

# ── Upload ────────────────────────────────────────────────────────────────────
def handle_upload(files):
    global _index_ready
    if not files:
        yield "⚠️ No files selected.", gr.update(interactive=False), gr.update(interactive=False)
        return

    yield "⏳ Extracting text…", gr.update(interactive=False), gr.update(interactive=False)

    try:
        s = load_documents([f.name for f in files])
        _index_ready = True
        info = (f"✅ **{s['docs']} file(s)** · **{s['pages']} pages** ready\n\n"
                + "\n".join(f"  📄 `{f}`" for f in s["files"]))
        yield info, gr.update(interactive=True), gr.update(interactive=True)
    except Exception as e:
        _index_ready = False
        yield f"❌ {e}", gr.update(interactive=False), gr.update(interactive=False)

# ── Streaming chat ────────────────────────────────────────────────────────────
def answer_question(question: str, history: list):
    question = question.strip()
    if not question:
        yield history, "", ""
        return

    if not _index_ready:
        msg = "⚠️ Please upload your legal documents first."
        yield history + [_msg("user", question), _msg("assistant", msg)], "", ""
        return

    # Show user message + placeholder while streaming starts
    yield (history + [_msg("user", question), _msg("assistant", "Searching your documents…")],
           "*Searching…*", "")

    accumulated = ""
    sources     = []
    lang        = "en"
    elapsed     = 0

    for chunk, src, lng, t in query_pipeline_stream(question):
        if src is not None:
            # Final metadata signal
            sources = src
            lang    = lng or "en"
            elapsed = t or 0
        else:
            accumulated += chunk
            # Only update every chunk — don't add cursor char (causes render issues)
            yield (history + [_msg("user", question),
                               _msg("assistant", accumulated)],
                   "*Generating…*", "")

    # Final state
    if not accumulated:
        accumulated = "⚠️ No response received. Please try again."

    meta = (f"**Language:** {LANG_FLAGS.get(lang, lang)}\n\n"
            f"**⏱ {elapsed}s**\n\n"
            f"{_fmt_sources(sources)}")

    yield (history + [_msg("user", question), _msg("assistant", accumulated)],
           meta, "")

def clear_all():
    _trans_cache.clear()
    return [], "*Response details will appear here.*", ""

# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600&family=JetBrains+Mono:wght@400&display=swap');

:root {
  --bg:      #0d0d0f;
  --surface: #141417;
  --card:    #1c1c22;
  --input:   #1e1e26;
  --border:  rgba(255,255,255,0.07);
  --accent:  #7c6af7;
  --accent2: #4fa3f7;
  --txt:     #e8e8f0;
  --txt2:    #8888a0;
  --txt3:    #555568;
  --r:       14px;
}

*, *::before, *::after { box-sizing: border-box; }
body, .gradio-container {
  font-family: 'Sora', sans-serif !important;
  background: var(--bg) !important;
  color: var(--txt) !important;
}
.gradio-container { max-width: 1280px !important; margin: 0 auto !important; padding: 0 !important; }
footer { display: none !important; }

/* grid bg */
.gradio-container::before {
  content:''; position:fixed; inset:0; z-index:-2;
  background: linear-gradient(rgba(124,106,247,.03) 1px,transparent 1px),
              linear-gradient(90deg,rgba(124,106,247,.03) 1px,transparent 1px);
  background-size: 48px 48px;
  animation: gridMove 20s linear infinite;
}
@keyframes gridMove { to { background-position: 48px 48px, 48px 48px; } }

/* orb */
.orb-wrap { position:fixed; top:-120px; right:-80px; z-index:-1;
            width:480px; height:480px; pointer-events:none; }
.orb { width:100%; height:100%; border-radius:50%;
  background: radial-gradient(circle at 40% 40%,
    rgba(124,106,247,.35) 0%, rgba(79,163,247,.18) 45%, transparent 70%);
  filter:blur(40px);
  animation: pulse 6s ease-in-out infinite; }
@keyframes pulse { 0%,100%{transform:scale(1) rotate(0);opacity:.8}
                   50%{transform:scale(1.15) rotate(15deg);opacity:1} }

/* header */
.hdr { text-align:center; padding:36px 24px 20px; animation:fadeD .6s ease both; }
.hdr h1 {
  font-size:2.4rem; font-weight:600; letter-spacing:-.03em; margin:0 0 6px;
  background:linear-gradient(135deg,#e8e8f0 0%,var(--accent) 60%,var(--accent2) 100%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
}
.hdr p { color:var(--txt2); font-size:.9rem; margin:0; }
.badge { display:inline-block; background:rgba(79,163,247,.12);
  border:1px solid rgba(79,163,247,.25); color:var(--accent2);
  padding:2px 10px; border-radius:20px; font-size:.72rem; font-weight:600; margin-left:8px; }
@keyframes fadeD { from{opacity:0;transform:translateY(-16px)} to{opacity:1;transform:none} }

/* layout */
.cols { display:flex; gap:16px; padding:0 20px 24px; }
.lcol { flex:0 0 290px; display:flex; flex-direction:column; gap:12px; }
.rcol { flex:1; display:flex; flex-direction:column; gap:12px; }

/* card */
.card {
  background:var(--card); border:1px solid var(--border);
  border-radius:var(--r); box-shadow:0 8px 32px rgba(0,0,0,.6);
  overflow:hidden; animation:fadeU .5s ease both;
}
@keyframes fadeU { from{opacity:0;transform:translateY(14px)} to{opacity:1;transform:none} }

/* upload */
.upzone { padding:16px; }
.upzone label { color:var(--txt2) !important; font-size:.75rem !important;
  text-transform:uppercase; letter-spacing:.08em; }
.upzone .upload-container {
  background:var(--input) !important;
  border:1.5px dashed rgba(124,106,247,.3) !important;
  border-radius:10px !important; transition:border-color .2s,background .2s; }
.upzone .upload-container:hover {
  border-color:var(--accent) !important;
  background:rgba(124,106,247,.06) !important; }

/* status */
.status { padding:12px 16px; font-size:.8rem; color:var(--txt2);
  border-top:1px solid var(--border); min-height:56px; line-height:1.6; }
.status p { margin:0 !important; }

/* tagline card */
.tagline { padding:18px; font-size:.85rem; color:var(--txt2); line-height:1.7; }
.tagline strong { color:var(--txt); }

/* chatbot */
#chat-col .chatbot { background:var(--surface) !important;
  border:none !important; border-radius:0 !important; }
#chat-col .message {
  font-family:'Sora',sans-serif !important; font-size:.92rem !important;
  line-height:1.65 !important; border-radius:12px !important;
  padding:13px 17px !important; animation:msgIn .25s ease both; }
@keyframes msgIn { from{opacity:0;transform:translateY(8px) scale(.98)}
                   to{opacity:1;transform:none} }
#chat-col .user .message {
  background:linear-gradient(135deg,rgba(124,106,247,.18),rgba(79,163,247,.12)) !important;
  border:1px solid rgba(124,106,247,.2) !important; color:var(--txt) !important; }
#chat-col .bot .message {
  background:var(--card) !important; border:1px solid var(--border) !important;
  color:var(--txt) !important; }

/* input row */
.irow { padding:10px 14px; border-top:1px solid var(--border);
  background:var(--surface); display:flex; align-items:flex-end; gap:8px; }
.irow textarea {
  font-family:'Sora',sans-serif !important; font-size:.9rem !important;
  background:var(--input) !important; border:1.5px solid var(--border) !important;
  border-radius:12px !important; color:var(--txt) !important;
  padding:11px 15px !important; resize:none !important;
  transition:border-color .2s,box-shadow .2s; }
.irow textarea:focus {
  border-color:var(--accent) !important;
  box-shadow:0 0 0 3px rgba(124,106,247,.15) !important; outline:none !important; }
.irow textarea::placeholder { color:var(--txt3) !important; }

/* buttons */
.btn-p {
  background:linear-gradient(135deg,var(--accent),var(--accent2)) !important;
  border:none !important; color:#fff !important;
  font-family:'Sora',sans-serif !important; font-weight:600 !important;
  font-size:.86rem !important; border-radius:10px !important;
  padding:10px 20px !important; white-space:nowrap;
  box-shadow:0 4px 16px rgba(124,106,247,.3) !important;
  transition:opacity .2s,transform .15s,box-shadow .2s; }
.btn-p:hover  { opacity:.9; transform:translateY(-1px);
  box-shadow:0 6px 20px rgba(124,106,247,.4) !important; }
.btn-p:active { transform:translateY(0); }
.btn-p:disabled { opacity:.35 !important; cursor:not-allowed !important; box-shadow:none !important; }

.btn-s {
  background:var(--card) !important; border:1px solid var(--border) !important;
  color:var(--txt2) !important; font-family:'Sora',sans-serif !important;
  font-size:.8rem !important; border-radius:8px !important;
  padding:5px 13px !important; transition:background .2s,color .2s; }
.btn-s:hover { background:rgba(255,255,255,.06) !important; color:var(--txt) !important; }

/* meta */
.meta { padding:16px 18px; font-size:.82rem; color:var(--txt2); }
.meta p { margin:0 0 5px; }
.meta b, .meta strong { color:var(--txt); }
.meta code {
  background:rgba(124,106,247,.12); color:var(--accent);
  padding:1px 6px; border-radius:4px;
  font-family:'JetBrains Mono',monospace; font-size:.78rem; }

::-webkit-scrollbar { width:4px; height:4px; }
::-webkit-scrollbar-thumb { background:rgba(255,255,255,.1); border-radius:2px; }
"""

# ── UI ────────────────────────────────────────────────────────────────────────
with gr.Blocks(title="LegalGPT", theme=gr.themes.Base(), css=CSS) as demo:

    gr.HTML("""
    <div class="orb-wrap"><div class="orb"></div></div>
    <div class="hdr">
      <h1>⚖️ LegalGPT</h1>
      <p>Upload legal PDFs · Ask in Tamil, Hindi or English
         <span class="badge">⚡ Streaming</span>
      </p>
    </div>
    """)

    with gr.Row(elem_classes="cols"):

        # ── Left panel ────────────────────────────────────────────────────
        with gr.Column(elem_classes="lcol card"):
            with gr.Group(elem_classes="upzone"):
                file_upload = gr.File(
                    label="Upload Legal PDFs",
                    file_types=[".pdf"],
                    file_count="multiple",
                    height=150,
                )
            upload_btn = gr.Button("⚡ Load Documents",
                                   variant="primary", elem_classes="btn-p", size="sm")
            index_status = gr.Markdown(
                value="Upload PDFs and click **Load Documents**",
                elem_classes="status",
            )
            gr.Markdown(
                "**Get accurate answers from your documents — zero hallucination.**\n\n"
                "Every answer is grounded strictly in the pages you upload. "
                "If it's not in your document, LegalGPT says so.\n\n"
                "*For informational use only — not legal advice.*",
                elem_classes="tagline",
            )

        # ── Right panel ───────────────────────────────────────────────────
        with gr.Column(elem_classes="rcol card", elem_id="chat-col"):
            chatbot = gr.Chatbot(
                label="", height=460,
                show_copy_button=True,
                type="messages",
                # No avatar_images — avoids broken image blank bubbles
                placeholder=(
                    "<div style='text-align:center;padding:48px;color:#555568'>"
                    "<div style='font-size:3rem'>⚖️</div>"
                    "<div style='color:#8888a0;margin-top:8px'>Upload documents, then ask a question</div>"
                    "<div style='font-size:.8rem;margin-top:6px'>Tamil · Hindi · English · Tanglish · Hinglish</div>"
                    "</div>"
                ),
            )
            with gr.Row(elem_classes="irow"):
                question_box = gr.Textbox(
                    placeholder="Ask your legal question…",
                    label="", lines=2, scale=5,
                    interactive=False, show_label=False,
                )
                with gr.Column(scale=1, min_width=100):
                    submit_btn = gr.Button("Send ➤", variant="primary",
                                           elem_classes="btn-p",
                                           interactive=False, size="lg")
                    clear_btn  = gr.Button("Clear", elem_classes="btn-s", size="sm")
            status_box = gr.Markdown(value="")

    with gr.Row(elem_classes="cols"):
        with gr.Column(elem_classes="card"):
            meta_panel = gr.Markdown(
                value="*Response details will appear here.*",
                elem_classes="meta",
            )

    # ── Events ────────────────────────────────────────────────────────────
    upload_btn.click(
        fn=handle_upload,
        inputs=[file_upload],
        outputs=[index_status, submit_btn, question_box],
    )

    submit_btn.click(
        fn=answer_question,
        inputs=[question_box, chatbot],
        outputs=[chatbot, meta_panel, status_box],
    ).then(fn=lambda: gr.update(value=""), outputs=question_box)

    question_box.submit(
        fn=answer_question,
        inputs=[question_box, chatbot],
        outputs=[chatbot, meta_panel, status_box],
    ).then(fn=lambda: gr.update(value=""), outputs=question_box)

    clear_btn.click(fn=clear_all, outputs=[chatbot, meta_panel, status_box])

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
        show_api=False,
        ssr_mode=False,
    )
