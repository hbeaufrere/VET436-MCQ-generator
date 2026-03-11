# VET436 MCQ Generator

An AI-powered multiple choice question generator for veterinary students. Upload lecture PDFs, PowerPoint slides, or text notes and generate practice exam questions on-the-fly using Claude.

## Features

- **Document upload** — supports PDF, PPTX, and TXT files
- **AI-generated MCQs** — Claude analyzes your course materials and creates exam-style questions
- **Instant feedback** — see the correct answer and explanation after each question
- **Topic focus** — optionally narrow questions to a specific topic
- **Full review** — review all questions with explanations after completing a quiz
- **Canvas-ready** — embeddable in Canvas LMS as an external link or iframe

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/hbeaufrere/VET436-MCQ-generator.git
cd VET436-MCQ-generator
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=some-random-string
```

### 3. Run locally

```bash
python app.py
```

Open http://localhost:5000 in your browser.

## Deploy to Render

1. Push this repo to GitHub
2. Create a new **Web Service** on [Render](https://render.com)
3. Connect your GitHub repo
4. Set the environment variable `ANTHROPIC_API_KEY`
5. Deploy — Render will auto-detect the `render.yaml` config

## Canvas LMS Integration

### Option A: External URL (simplest)

1. Deploy the app (e.g., to Render)
2. In Canvas, go to your course → Modules
3. Add an **External URL** item with the deployed app URL
4. Students click the link to access the quiz generator

### Option B: Embed in a Page

1. In Canvas, create or edit a Page
2. Switch to HTML editor
3. Add: `<iframe src="https://your-app-url.onrender.com/quiz" width="100%" height="800" frameborder="0"></iframe>`

## How It Works

1. **Instructor uploads** lecture materials (PDF/PPTX/TXT)
2. Text is extracted and stored in a local SQLite database
3. **Students select** documents and number of questions
4. The app sends the extracted text to **Claude** with a structured prompt
5. Claude generates MCQs with correct answers and explanations
6. Students answer questions and get **instant feedback with explanations**
7. A final score and full review are shown at the end

## Tech Stack

- **Backend**: Python / Flask
- **AI**: Anthropic Claude API
- **Document parsing**: pdfplumber (PDF), python-pptx (PowerPoint)
- **Database**: SQLite
- **Frontend**: Vanilla HTML/CSS/JS
- **Deployment**: Gunicorn / Render
