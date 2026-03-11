import os
import json
import sqlite3
import hashlib
from pathlib import Path

from flask import (
    Flask, render_template, request, jsonify, redirect, url_for, flash, g
)
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import anthropic
import pdfplumber
from pptx import Presentation

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

UPLOAD_FOLDER = Path(__file__).parent / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

ALLOWED_EXTENSIONS = {"pdf", "pptx", "ppt", "txt"}

DATABASE = Path(__file__).parent / "mcq.db"

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(str(DATABASE))
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(str(DATABASE))
    db.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_hash TEXT NOT NULL UNIQUE,
            text_content TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS quiz_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            questions_json TEXT NOT NULL,
            score INTEGER,
            total INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );
    """)
    db.close()


init_db()

# ---------------------------------------------------------------------------
# Document parsing
# ---------------------------------------------------------------------------

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_pdf(filepath):
    text_parts = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts)


def extract_text_pptx(filepath):
    prs = Presentation(filepath)
    text_parts = []
    for slide in prs.slides:
        slide_texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    line = paragraph.text.strip()
                    if line:
                        slide_texts.append(line)
        if slide_texts:
            text_parts.append("\n".join(slide_texts))
    return "\n\n".join(text_parts)


def extract_text_txt(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def extract_text(filepath):
    ext = Path(filepath).suffix.lower()
    if ext == ".pdf":
        return extract_text_pdf(filepath)
    elif ext in (".pptx", ".ppt"):
        return extract_text_pptx(filepath)
    elif ext == ".txt":
        return extract_text_txt(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def file_hash(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

# ---------------------------------------------------------------------------
# Claude API – MCQ generation
# ---------------------------------------------------------------------------

def generate_mcqs(text_content, num_questions=10, topic_focus=None):
    """Call Claude to generate MCQs from document text."""
    client = anthropic.Anthropic()

    focus_instruction = ""
    if topic_focus:
        focus_instruction = f"\nFocus the questions specifically on: {topic_focus}"

    # Truncate very long documents to fit context
    max_chars = 80_000
    if len(text_content) > max_chars:
        text_content = text_content[:max_chars] + "\n\n[Content truncated...]"

    prompt = f"""You are an expert veterinary science educator creating exam-style multiple choice questions (MCQs) for veterinary students.

Based on the following lecture/course material, generate exactly {num_questions} high-quality MCQs.{focus_instruction}

Requirements for each question:
- Write a clear, specific question stem
- Provide exactly 4 answer options labeled A, B, C, D
- Exactly one option must be correct
- Include plausible distractors that test understanding, not just recall
- After the correct answer, provide a brief explanation (2-3 sentences) of WHY the correct answer is right and why key distractors are wrong

Return your response as a JSON array with this exact structure:
[
  {{
    "question": "The question text",
    "options": {{
      "A": "First option",
      "B": "Second option",
      "C": "Third option",
      "D": "Fourth option"
    }},
    "correct_answer": "A",
    "explanation": "Explanation of why A is correct and why other options are incorrect."
  }}
]

Return ONLY the JSON array, no other text.

--- COURSE MATERIAL ---
{text_content}
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    # Extract JSON from response (handle markdown code blocks)
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        # Remove first and last lines (code block markers)
        lines = [l for l in lines if not l.strip().startswith("```")]
        response_text = "\n".join(lines)

    return json.loads(response_text)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    db = get_db()
    documents = db.execute(
        "SELECT id, filename, uploaded_at FROM documents ORDER BY uploaded_at DESC"
    ).fetchall()
    return render_template("index.html", documents=documents)


@app.route("/upload", methods=["POST"])
def upload():
    if "files" not in request.files:
        flash("No files selected.", "error")
        return redirect(url_for("index"))

    files = request.files.getlist("files")
    uploaded_count = 0

    for file in files:
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            try:
                fhash = file_hash(filepath)
                text = extract_text(filepath)

                if not text.strip():
                    flash(f"{filename}: Could not extract text.", "error")
                    os.remove(filepath)
                    continue

                db = get_db()
                try:
                    db.execute(
                        "INSERT INTO documents (filename, file_hash, text_content) VALUES (?, ?, ?)",
                        (filename, fhash, text),
                    )
                    db.commit()
                    uploaded_count += 1
                except sqlite3.IntegrityError:
                    flash(f"{filename}: Already uploaded.", "warning")
            except Exception as e:
                flash(f"{filename}: Error processing — {e}", "error")
            finally:
                # Remove the file after extracting text (we only need the text)
                if os.path.exists(filepath):
                    os.remove(filepath)

    if uploaded_count:
        flash(f"Successfully uploaded {uploaded_count} document(s).", "success")

    return redirect(url_for("index"))


@app.route("/delete/<int:doc_id>", methods=["POST"])
def delete_document(doc_id):
    db = get_db()
    db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    db.commit()
    flash("Document removed.", "success")
    return redirect(url_for("index"))


@app.route("/quiz")
def quiz():
    db = get_db()
    documents = db.execute(
        "SELECT id, filename FROM documents ORDER BY uploaded_at DESC"
    ).fetchall()
    return render_template("quiz.html", documents=documents)


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """API endpoint to generate MCQs."""
    data = request.get_json()
    doc_ids = data.get("document_ids", [])
    num_questions = min(int(data.get("num_questions", 10)), 30)
    topic_focus = data.get("topic_focus", "").strip() or None

    if not doc_ids:
        return jsonify({"error": "Please select at least one document."}), 400

    db = get_db()
    placeholders = ",".join("?" for _ in doc_ids)
    rows = db.execute(
        f"SELECT text_content, filename FROM documents WHERE id IN ({placeholders})",
        doc_ids,
    ).fetchall()

    if not rows:
        return jsonify({"error": "Documents not found."}), 404

    # Combine text from selected documents
    combined_text = "\n\n".join(
        f"--- {row['filename']} ---\n{row['text_content']}" for row in rows
    )

    try:
        questions = generate_mcqs(combined_text, num_questions, topic_focus)
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse generated questions. Please try again."}), 500
    except anthropic.APIError as e:
        return jsonify({"error": f"AI service error: {e.message}"}), 502

    # Save quiz session
    doc_id = doc_ids[0] if len(doc_ids) == 1 else None
    db.execute(
        "INSERT INTO quiz_sessions (document_id, questions_json, total) VALUES (?, ?, ?)",
        (doc_id, json.dumps(questions), len(questions)),
    )
    db.commit()

    return jsonify({"questions": questions})


@app.route("/api/documents")
def api_documents():
    db = get_db()
    docs = db.execute(
        "SELECT id, filename, uploaded_at FROM documents ORDER BY uploaded_at DESC"
    ).fetchall()
    return jsonify([dict(d) for d in docs])


# ---------------------------------------------------------------------------
# Canvas LTI / Embedding support
# ---------------------------------------------------------------------------

@app.after_request
def allow_iframe_embedding(response):
    """Allow the app to be embedded in Canvas iframes."""
    response.headers["X-Frame-Options"] = "ALLOWALL"
    response.headers.pop("X-Frame-Options", None)
    response.headers["Content-Security-Policy"] = "frame-ancestors *"
    return response


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
