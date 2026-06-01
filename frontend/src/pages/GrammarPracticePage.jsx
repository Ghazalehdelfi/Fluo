import { useState, useEffect, useRef } from "react";
import CreditIcon from "../components/CreditIcon";
import { useApp } from "../context/AppContext.jsx";

export default function GrammarPracticePage() {
  const {
    apiFetch,
    currentLanguageSlug,
    practiceGrammarId,
    setPracticeGrammarId,
    invalidateCache,
    currentLanguageId,
    fetchGrammar,
  } = useApp();

  const [view, setView] = useState("setup"); // 'setup' | 'loading' | 'active' | 'results'
  const [grammarConcepts, setGrammarConcepts] = useState([]);
  const [selectedGrammarId, setSelectedGrammarId] = useState(
    practiceGrammarId || null,
  );
  const [sessionId, setSessionId] = useState(null);
  const [grammarConcept, setGrammarConcept] = useState("");
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [userAnswer, setUserAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [results, setResults] = useState([]);
  const [finalScore, setFinalScore] = useState(null);
  const [error, setError] = useState(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    fetchGrammar(currentLanguageId).then((data) =>
      setGrammarConcepts(data || []),
    );
    // If arriving with a pre-selected grammar id (e.g. from LanguagePage), skip setup
    if (practiceGrammarId) {
      startSession(practiceGrammarId);
    }
  }, []);

  async function startSession(grammarId) {
    const id = grammarId || selectedGrammarId;
    if (!id) return;
    setView("loading");
    setError(null);
    try {
      const resp = await apiFetch(`/api/grammar/${id}/start-practice`, {
        method: "POST",
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        setError(data.detail || "Failed to generate practice questions");
        setView("error");
        return;
      }
      const data = await resp.json();
      setSessionId(data.session_id);
      setGrammarConcept(data.grammar_concept);
      setQuestions(data.questions);
      setCurrentIndex(0);
      setUserAnswer("");
      setFeedback(null);
      setResults([]);
      setView("active");
    } catch {
      setError("Network error — please try again");
      setView("error");
    }
  }

  async function submitAnswer() {
    if (!userAnswer.trim() || submitting) return;
    setSubmitting(true);
    try {
      const resp = await apiFetch(
        `/api/grammar-practice/${sessionId}/submit-answer`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question_index: currentIndex,
            user_answer: userAnswer.trim(),
          }),
        },
      );
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        alert(data.detail || "Failed to evaluate answer");
        return;
      }
      const data = await resp.json();
      setFeedback(data);
      setResults((r) => [
        ...r,
        {
          question: questions[currentIndex],
          userAnswer: userAnswer.trim(),
          feedback: data,
        },
      ]);
    } catch {
      alert("Network error — please try again");
    } finally {
      setSubmitting(false);
    }
  }

  async function nextQuestion() {
    const next = currentIndex + 1;
    if (next >= questions.length) {
      await endSession();
    } else {
      setCurrentIndex(next);
      setUserAnswer("");
      setFeedback(null);
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  }

  async function endSession() {
    try {
      const resp = await apiFetch(`/api/grammar-practice/${sessionId}/end`, {
        method: "POST",
      });
      if (resp.ok) {
        const data = await resp.json();
        setFinalScore(data);
        invalidateCache(currentLanguageId, "grammar", "stats", "dashboard");
      }
    } catch {}
    setView("results");
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      submitAnswer();
    }
  }

  function goBackToSetup() {
    setPracticeGrammarId(null);
    setSelectedGrammarId(null);
    setView("setup");
  }

  // ── Setup view ────────────────────────────────────────────
  if (view === "setup") {
    return (
      <div>
        <header className="mb-10">
          <h2
            className="text-4xl font-bold tracking-tight"
            style={{ color: "var(--dark)" }}
          >
            Grammar Practice
          </h2>
          <p className="mt-2" style={{ color: "var(--accent1)" }}>
            Choose a concept to practice
          </p>
        </header>

        <div className="max-w-2xl space-y-6">
          {grammarConcepts.length === 0 ? (
            <div
              className="rounded-2xl p-8 text-center"
              style={{
                background: "var(--white)",
                boxShadow: "0 4px 16px rgba(45,52,51,0.06)",
              }}
            >
              <span
                className="material-symbols-outlined text-4xl mb-3 block"
                style={{ color: "var(--outline-variant)" }}
              >
                school
              </span>
              <p
                className="text-sm"
                style={{ color: "var(--outline-variant)" }}
              >
                No grammar concepts yet — upload some notes first.
              </p>
            </div>
          ) : (
            <div
              className="rounded-2xl overflow-hidden"
              style={{
                background: "var(--white)",
                boxShadow: "0 4px 16px rgba(45,52,51,0.06)",
              }}
            >
              {grammarConcepts.map((g, i) => (
                <div
                  key={g.id}
                  onClick={() =>
                    setSelectedGrammarId(
                      g.id === selectedGrammarId ? null : g.id,
                    )
                  }
                  className="flex items-center justify-between px-6 py-4 cursor-pointer transition-all"
                  style={{
                    background:
                      selectedGrammarId === g.id
                        ? "var(--primary-container)"
                        : "transparent",
                    borderTop:
                      i > 0
                        ? "1px solid var(--surface-container-high)"
                        : "none",
                  }}
                >
                  <div className="flex-1 min-w-0">
                    <p
                      className="text-sm font-medium"
                      style={{ color: "var(--dark)" }}
                    >
                      {g.concept_name}
                    </p>
                    {g.description && (
                      <p
                        className="text-xs mt-0.5 truncate"
                        style={{ color: "var(--outline-variant)" }}
                      >
                        {g.description}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-3 ml-4">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium fluency-${g.fluency_level}`}
                    >
                      {g.fluency_level}
                    </span>
                    {selectedGrammarId === g.id && (
                      <span
                        className="material-symbols-outlined text-base"
                        style={{ color: "var(--primary)" }}
                      >
                        check_circle
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          <button
            onClick={() => startSession()}
            disabled={!selectedGrammarId}
            className="btn-primary w-full py-4 rounded-xl font-semibold text-lg flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span className="material-symbols-outlined">exercise</span>
            Start Practice
            <CreditIcon />
          </button>
        </div>
      </div>
    );
  }

  // ── Render highlighted segments ────────────────────────────
  function renderHighlighted(segments) {
    if (!segments || segments.length === 0) return null;
    return (
      <span>
        {segments.map((seg, i) =>
          seg.highlight ? (
            <span
              key={i}
              style={{
                color: "var(--primary)",
                textDecoration: "underline",
                fontWeight: 600,
              }}
            >
              {seg.text}
            </span>
          ) : (
            <span key={i}>{seg.text}</span>
          ),
        )}
      </span>
    );
  }

  // ── Loading view ──────────────────────────────────────────
  if (view === "loading") {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div
          className="w-12 h-12 rounded-full border-4 animate-spin"
          style={{
            borderColor: "var(--surface-container-high)",
            borderTopColor: "var(--primary)",
          }}
        />
        <p className="text-sm font-medium" style={{ color: "var(--accent1)" }}>
          Generating practice exercises…
        </p>
      </div>
    );
  }

  // ── Error view ────────────────────────────────────────────
  if (view === "error") {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <p className="text-sm" style={{ color: "#a83836" }}>
          {error}
        </p>
        <div className="flex gap-3">
          <button
            onClick={startSession}
            className="btn-primary px-6 py-2 rounded-xl text-sm font-medium"
          >
            Retry
          </button>
          <button
            onClick={goBackToSetup}
            className="btn-secondary px-6 py-2 rounded-xl text-sm font-medium"
          >
            Back to Grammar
          </button>
        </div>
      </div>
    );
  }

  // ── Results view ──────────────────────────────────────────
  if (view === "results") {
    const correct =
      finalScore?.correct_count ??
      results.filter((r) => r.feedback?.is_correct).length;
    const total = finalScore?.total_questions ?? results.length;
    const pct = total > 0 ? Math.round((correct / total) * 100) : 0;
    const newFluency = finalScore?.fluency_level;

    return (
      <div className="max-w-2xl mx-auto py-8 space-y-6">
        {/* Score card */}
        <div
          className="rounded-[2rem] p-8 text-center space-y-3"
          style={{
            background: "var(--white)",
            boxShadow: "0 4px 24px rgba(45,52,51,0.08)",
          }}
        >
          <p
            className="text-sm font-medium uppercase tracking-wider"
            style={{ color: "var(--accent1)" }}
          >
            {grammarConcept}
          </p>
          <div
            className="text-6xl font-bold"
            style={{ color: "var(--primary)" }}
          >
            {correct}
            <span
              className="text-3xl font-normal"
              style={{ color: "var(--outline-variant)" }}
            >
              /{total}
            </span>
          </div>
          <p className="text-lg font-medium" style={{ color: "var(--dark)" }}>
            {pct >= 70
              ? "Great work!"
              : pct >= 50
                ? "Good effort!"
                : "Keep practicing!"}
          </p>
          {newFluency && (
            <span
              className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium fluency-${newFluency}`}
            >
              <span className="material-symbols-outlined text-sm">
                trending_up
              </span>
              Fluency updated to {newFluency}
            </span>
          )}
        </div>

        {/* Question review */}
        <div className="space-y-3">
          {results.map((r, i) => (
            <div
              key={i}
              className="rounded-[1.25rem] p-5 space-y-2"
              style={{
                background: "var(--white)",
                border: `1.5px solid ${r.feedback?.is_correct ? "#bbf7d0" : "#fecaca"}`,
              }}
            >
              <div className="flex items-start gap-2">
                <span
                  className="material-symbols-outlined text-base mt-0.5"
                  style={{
                    color: r.feedback?.is_correct ? "#16a34a" : "#dc2626",
                  }}
                >
                  {r.feedback?.is_correct ? "check_circle" : "cancel"}
                </span>
                <div className="flex-1 space-y-1">
                  <p
                    className="text-xs font-medium"
                    style={{ color: "var(--outline-variant)" }}
                  >
                    Q{i + 1} ·{" "}
                    {r.question.type === "translation"
                      ? "Translation"
                      : "Error Correction"}
                  </p>
                  <p className="text-sm" style={{ color: "var(--dark)" }}>
                    {r.question.question_text}
                  </p>
                  <p
                    className="text-sm italic"
                    style={{ color: "var(--accent1)" }}
                  >
                    Your answer: {r.userAnswer}
                  </p>
                  {!r.feedback?.is_correct && (
                    <p
                      className="text-sm font-medium"
                      style={{ color: "var(--primary)" }}
                    >
                      Correct:{" "}
                      {renderHighlighted(r.feedback?.highlighted_segments) ||
                        r.feedback?.correct_answer}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Actions */}
        <div className="flex gap-3 justify-center">
          <button
            onClick={() => startSession(selectedGrammarId)}
            className="btn-primary px-6 py-2.5 rounded-xl text-sm font-medium"
          >
            Practice Again
          </button>
          <button
            onClick={goBackToSetup}
            className="btn-secondary px-6 py-2.5 rounded-xl text-sm font-medium"
          >
            Choose Another
          </button>
        </div>
      </div>
    );
  }

  // ── Active view ───────────────────────────────────────────
  const question = questions[currentIndex];
  const progress = (currentIndex / questions.length) * 100;
  const isLast = currentIndex === questions.length - 1;

  return (
    <div className="max-w-2xl mx-auto py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={goBackToSetup}
          className="flex items-center gap-1 text-sm transition-colors"
          style={{ color: "var(--outline-variant)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--dark)")}
          onMouseLeave={(e) =>
            (e.currentTarget.style.color = "var(--outline-variant)")
          }
        >
          <span className="material-symbols-outlined text-base">
            arrow_back
          </span>
          Grammar Practice
        </button>
        <p className="text-sm font-medium" style={{ color: "var(--accent1)" }}>
          {grammarConcept}
        </p>
        <p
          className="text-sm font-semibold"
          style={{ color: "var(--primary)" }}
        >
          {currentIndex + 1} / {questions.length}
        </p>
      </div>

      {/* Progress bar */}
      <div
        className="h-2 rounded-full overflow-hidden"
        style={{ background: "var(--surface-container-high)" }}
      >
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${progress}%`, background: "var(--primary)" }}
        />
      </div>

      {/* Question card */}
      <div
        className="rounded-[2rem] p-8 space-y-5"
        style={{
          background: "var(--white)",
          boxShadow: "0 4px 24px rgba(45,52,51,0.08)",
        }}
      >
        {/* Type badge */}
        <span
          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium"
          style={{
            background:
              question.type === "translation"
                ? "var(--primary-container)"
                : "#fef3c7",
            color:
              question.type === "translation" ? "var(--primary)" : "#92400e",
          }}
        >
          <span className="material-symbols-outlined text-sm">
            {question.type === "translation" ? "translate" : "edit_note"}
          </span>
          {question.type === "translation" ? "Translation" : "Error Correction"}
        </span>

        {/* Question text */}
        <p className="text-lg font-medium" style={{ color: "var(--dark)" }}>
          {question.question_text}
        </p>

        {/* Wrong sentence for correction type */}
        {question.type === "correction" && question.wrong_sentence && (
          <div
            className="rounded-xl px-4 py-3 flex items-start gap-2"
            style={{ background: "#fef2f2", border: "1px solid #fecaca" }}
          >
            <span
              className="material-symbols-outlined text-base mt-0.5"
              style={{ color: "#dc2626" }}
            >
              error
            </span>
            <p className="text-sm font-medium" style={{ color: "#7f1d1d" }}>
              {question.wrong_sentence}
            </p>
          </div>
        )}

        {/* Answer input */}
        {!feedback && (
          <div className="space-y-3">
            <textarea
              ref={textareaRef}
              value={userAnswer}
              onChange={(e) => setUserAnswer(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`Type your ${question.type === "translation" ? "translation" : "corrected sentence"} here…`}
              rows={3}
              autoFocus
              className="w-full rounded-xl px-4 py-3 text-sm resize-none outline-none transition-all"
              style={{
                background: "var(--surface-container-low)",
                border: "1.5px solid var(--surface-container-high)",
                color: "var(--dark)",
              }}
              onFocus={(e) =>
                (e.currentTarget.style.borderColor = "var(--primary)")
              }
              onBlur={(e) =>
                (e.currentTarget.style.borderColor =
                  "var(--surface-container-high)")
              }
            />
            <div className="flex items-center justify-between">
              <p
                className="text-xs"
                style={{ color: "var(--outline-variant)" }}
              >
                ⌘↵ to submit
              </p>
              <button
                onClick={submitAnswer}
                disabled={!userAnswer.trim() || submitting}
                className="btn-primary px-6 py-2 rounded-xl text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? "Checking…" : "Submit"}
              </button>
            </div>
          </div>
        )}

        {/* Feedback panel */}
        {feedback && (
          <div
            className="rounded-xl p-5 space-y-4"
            style={{
              background: feedback.is_correct ? "#f0fdf4" : "#fef2f2",
              border: `1.5px solid ${feedback.is_correct ? "#bbf7d0" : "#fecaca"}`,
            }}
          >
            {/* Result indicator */}
            <div className="flex items-center gap-2">
              <span
                className="material-symbols-outlined"
                style={{
                  color: feedback.is_correct ? "#16a34a" : "#dc2626",
                  fontSize: "1.5rem",
                }}
              >
                {feedback.is_correct ? "check_circle" : "cancel"}
              </span>
              <p
                className="text-sm font-semibold"
                style={{ color: feedback.is_correct ? "#15803d" : "#b91c1c" }}
              >
                {feedback.feedback}
              </p>
            </div>

            {/* Correct answer with highlighted segments */}
            <div className="space-y-1">
              <p
                className="text-xs font-medium uppercase tracking-wider"
                style={{ color: "var(--outline-variant)" }}
              >
                Correct answer
              </p>
              <p
                className="text-base font-medium"
                style={{ color: "var(--dark)" }}
              >
                {feedback.highlighted_segments &&
                feedback.highlighted_segments.length > 0
                  ? renderHighlighted(feedback.highlighted_segments)
                  : feedback.correct_answer}
              </p>
            </div>

            {/* Explanation */}
            {feedback.explanation && (
              <div
                className="rounded-lg px-4 py-3"
                style={{ background: "rgba(67,101,101,0.07)" }}
              >
                <p className="text-sm" style={{ color: "var(--primary)" }}>
                  <span className="font-semibold">Rule: </span>
                  {feedback.explanation}
                </p>
              </div>
            )}

            {/* Next / Finish button */}
            <div className="flex justify-end">
              <button
                onClick={nextQuestion}
                className="btn-primary px-6 py-2 rounded-xl text-sm font-medium flex items-center gap-2"
              >
                {isLast ? "See Results" : "Next Question"}
                <span className="material-symbols-outlined text-base">
                  arrow_forward
                </span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Mini progress dots */}
      <div className="flex justify-center gap-1.5 flex-wrap">
        {questions.map((_, i) => {
          const done = i < results.length;
          const correct = done && results[i]?.feedback?.is_correct;
          return (
            <div
              key={i}
              className="w-2.5 h-2.5 rounded-full transition-all"
              style={{
                background: done
                  ? correct
                    ? "#16a34a"
                    : "#dc2626"
                  : i === currentIndex
                    ? "var(--primary)"
                    : "var(--surface-container-high)",
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
