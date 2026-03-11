let questions = [];
let currentIndex = 0;
let userAnswers = {};
let revealed = {};

function escapeHTML(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// ----- Setup & Generation -----

const setupForm = document.getElementById("quizSetupForm");
if (setupForm) {
    setupForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const numQuestions = parseInt(document.getElementById("numQuestions").value);
        const topicFocus = document.getElementById("topicFocus").value.trim();

        document.getElementById("setupPanel").style.display = "none";
        document.getElementById("loadingPanel").style.display = "block";

        try {
            const resp = await fetch("/api/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    num_questions: numQuestions,
                    topic_focus: topicFocus || null,
                }),
            });

            const data = await resp.json();

            if (!resp.ok) {
                throw new Error(data.error || "Generation failed.");
            }

            questions = data.questions;
            currentIndex = 0;
            userAnswers = {};
            revealed = {};
            startQuiz();
        } catch (err) {
            alert("Error: " + err.message);
            document.getElementById("loadingPanel").style.display = "none";
            document.getElementById("setupPanel").style.display = "block";
        }
    });
}

// ----- Quiz Logic -----

function startQuiz() {
    document.getElementById("loadingPanel").style.display = "none";
    document.getElementById("quizPanel").style.display = "block";
    document.getElementById("totalQ").textContent = questions.length;
    renderQuestion();
}

function renderQuestion() {
    const q = questions[currentIndex];
    document.getElementById("currentQ").textContent = currentIndex + 1;
    document.getElementById("questionNumber").textContent = `Question ${currentIndex + 1}`;
    document.getElementById("questionText").textContent = q.question;

    // Progress bar
    const pct = ((currentIndex + 1) / questions.length) * 100;
    document.getElementById("progressBar").style.width = pct + "%";

    // Options
    const optionsList = document.getElementById("optionsList");
    optionsList.innerHTML = "";

    const isRevealed = revealed[currentIndex];

    for (const [letter, text] of Object.entries(q.options)) {
        const btn = document.createElement("button");
        btn.className = "option-btn";
        btn.innerHTML = `<span class="option-letter">${escapeHTML(letter)}</span><span class="option-text">${escapeHTML(text)}</span>`;

        if (isRevealed) {
            btn.classList.add("disabled");
            if (letter === q.correct_answer) {
                btn.classList.add("correct");
            } else if (letter === userAnswers[currentIndex]) {
                btn.classList.add("incorrect");
            }
        } else if (userAnswers[currentIndex] === letter) {
            btn.classList.add("selected");
        }

        if (!isRevealed) {
            btn.addEventListener("click", () => selectOption(letter));
        }

        optionsList.appendChild(btn);
    }

    // Explanation
    const expBox = document.getElementById("explanationBox");
    if (isRevealed) {
        document.getElementById("explanationText").textContent = q.explanation;
        expBox.style.display = "block";
    } else {
        expBox.style.display = "none";
    }

    // Navigation buttons
    document.getElementById("prevBtn").style.display = currentIndex > 0 ? "inline-block" : "none";

    const isLast = currentIndex === questions.length - 1;
    document.getElementById("nextBtn").style.display = isLast ? "none" : "inline-block";
    document.getElementById("finishBtn").style.display = isLast ? "inline-block" : "none";
}

function selectOption(letter) {
    userAnswers[currentIndex] = letter;
    revealed[currentIndex] = true;
    renderQuestion();
}

function nextQuestion() {
    if (currentIndex < questions.length - 1) {
        currentIndex++;
        renderQuestion();
        window.scrollTo({ top: 0, behavior: "smooth" });
    }
}

function prevQuestion() {
    if (currentIndex > 0) {
        currentIndex--;
        renderQuestion();
        window.scrollTo({ top: 0, behavior: "smooth" });
    }
}

// ----- Results -----

function showResults() {
    document.getElementById("quizPanel").style.display = "none";
    document.getElementById("resultsPanel").style.display = "block";

    let correct = 0;
    questions.forEach((q, i) => {
        if (userAnswers[i] === q.correct_answer) correct++;
    });

    document.getElementById("scoreNumber").textContent = correct;
    document.getElementById("scoreDenom").textContent = questions.length;
    document.getElementById("scorePercent").textContent =
        Math.round((correct / questions.length) * 100) + "%";

    // Review each question
    const reviewSection = document.getElementById("reviewSection");
    reviewSection.innerHTML = "<h3>Review All Questions</h3>";

    questions.forEach((q, i) => {
        const isCorrect = userAnswers[i] === q.correct_answer;
        const div = document.createElement("div");
        div.className = `review-item ${isCorrect ? "review-correct" : "review-incorrect"}`;

        let html = `<div class="review-question">${i + 1}. ${escapeHTML(q.question)}</div>`;

        if (!isCorrect && userAnswers[i]) {
            html += `<div class="review-answer your-answer">Your answer: ${escapeHTML(userAnswers[i])}. ${escapeHTML(q.options[userAnswers[i]])}</div>`;
        } else if (!userAnswers[i]) {
            html += `<div class="review-answer your-answer">Not answered</div>`;
        }

        html += `<div class="review-answer correct-answer">Correct answer: ${escapeHTML(q.correct_answer)}. ${escapeHTML(q.options[q.correct_answer])}</div>`;
        html += `<div class="review-explanation">${escapeHTML(q.explanation)}</div>`;

        div.innerHTML = html;
        reviewSection.appendChild(div);
    });

    window.scrollTo({ top: 0, behavior: "smooth" });
}

function resetQuiz() {
    questions = [];
    currentIndex = 0;
    userAnswers = {};
    revealed = {};

    document.getElementById("resultsPanel").style.display = "none";
    document.getElementById("quizPanel").style.display = "none";
    document.getElementById("setupPanel").style.display = "block";
}
