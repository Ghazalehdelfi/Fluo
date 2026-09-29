import { useState, useEffect, useRef } from "react";
import CreditIcon from "../components/CreditIcon";
import { useApp } from "../context/AppContext.jsx";
import {
  Page,
  PageHeader,
  Card,
  Button,
  EmptyState,
  LoadingState,
  ProgressBar,
  FluencyBadge,
  Eyebrow,
  SectionTitle,
  ResultSummary,
  ResultRow,
} from "../components/ui/index.jsx";

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
  const [conceptsLoading, setConceptsLoading] = useState(true);
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
    fetchGrammar(currentLanguageId)
      .then((data) => setGrammarConcepts(data || []))
      .finally(() => setConceptsLoading(false));
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
      <Page>
        <PageHeader
          title="Grammar Practice"
          subtitle="Choose a concept to practice"
        />

        <div className="space-y-6">
          {conceptsLoading ? (
            <Card>
              <LoadingState text="Loading grammar concepts…" />
            </Card>
          ) : grammarConcepts.length === 0 ? (
            <Card>
              <EmptyState
                icon="school"
                title="No grammar concepts yet"
                description="Upload some notes first to start practicing grammar."
              />
            </Card>
          ) : (
            <Card padding="md">
              <SectionTitle>Choose a concept</SectionTitle>
              <div className="space-y-2">
                {grammarConcepts.map((g) => {
                  const active = selectedGrammarId === g.id;
                  return (
                    <Card
                      key={g.id}
                      variant="tonal"
                      padding="sm"
                      interactive
                      selected={active}
                      className="!rounded-2xl flex items-center justify-between gap-4"
                      onClick={() => setSelectedGrammarId(active ? null : g.id)}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-[var(--dark)]">{g.concept_name}</p>
                        {g.description && (
                          <p className="text-xs mt-0.5 truncate text-[var(--accent1)]">{g.description}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <FluencyBadge level={g.fluency_level} />
                        <span
                          className="material-symbols-outlined text-base"
                          style={{ color: active ? "var(--primary)" : "var(--outline-variant)" }}
                        >
                          {active ? "check_circle" : "radio_button_unchecked"}
                        </span>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </Card>
          )}

          <Button size="xl" full icon="exercise" onClick={() => startSession()} disabled={conceptsLoading || !selectedGrammarId}>
            Start Practice
            <CreditIcon />
          </Button>
        </div>
      </Page>
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
      <Page>
        <LoadingState text="Generating practice exercises…" />
      </Page>
    );
  }

  // ── Error view ────────────────────────────────────────────
  if (view === "error") {
    return (
      <Page>
        <Card>
          <EmptyState
            icon="error"
            title="Something went wrong"
            description={error}
            action={
              <div className="flex gap-3">
                <Button onClick={startSession}>Retry</Button>
                <Button variant="secondary" onClick={goBackToSetup}>Back to Grammar</Button>
              </div>
            }
          />
        </Card>
      </Page>
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
      <Page>
        <PageHeader
          eyebrow="Session Complete"
          title="Practice Results"
          subtitle={grammarConcept}
          actions={
            <>
              <Button onClick={() => startSession(selectedGrammarId)}>Practice Again</Button>
              <Button variant="secondary" onClick={goBackToSetup}>Choose Another</Button>
            </>
          }
        />
        <ResultSummary total={total} correct={correct} totalLabel="Questions" />

        <Card variant="tonal">
          <SectionTitle
            actions={
              newFluency && (
                <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium fluency-${newFluency}`}>
                  <span className="material-symbols-outlined text-sm">trending_up</span>
                  Fluency updated to {newFluency}
                </span>
              )
            }
          >
            Review · {pct >= 70 ? "Great work!" : pct >= 50 ? "Good effort!" : "Keep practicing!"}
          </SectionTitle>
          <div className="space-y-3">
            {results.map((r, i) => (
              <ResultRow key={i} correct={r.feedback?.is_correct}>
                <div className="flex-1 space-y-1 min-w-0">
                  <Eyebrow className="!text-[10px]">
                    Q{i + 1} · {r.question.type === "translation" ? "Translation" : "Error Correction"}
                  </Eyebrow>
                  <p className="text-sm text-[var(--dark)]">{r.question.question_text}</p>
                  <p className="text-sm italic text-[var(--accent1)]">Your answer: {r.userAnswer}</p>
                  {!r.feedback?.is_correct && (
                    <p className="text-sm font-medium text-[var(--primary)]">
                      Correct:{" "}
                      {renderHighlighted(r.feedback?.highlighted_segments) || r.feedback?.correct_answer}
                    </p>
                  )}
                </div>
              </ResultRow>
            ))}
          </div>
        </Card>
      </Page>
    );
  }

  // ── Active view ───────────────────────────────────────────
  const question = questions[currentIndex];
  const progress = (currentIndex / questions.length) * 100;
  const isLast = currentIndex === questions.length - 1;

  return (
    <Page>
      <PageHeader
        onBack={goBackToSetup}
        eyebrow={`Question ${currentIndex + 1} of ${questions.length}`}
        title="Grammar Practice"
        subtitle={grammarConcept}
        className="!mb-6"
      />
      <div className="space-y-6">
      <ProgressBar value={progress} />

      {/* Question card */}
      <Card className="space-y-5">
        {/* Type badge */}
        <Eyebrow tone="primary" className="flex items-center gap-1.5">
          <span className="material-symbols-outlined text-sm">
            {question.type === "translation" ? "translate" : "edit_note"}
          </span>
          {question.type === "translation" ? "Translation" : "Error Correction"}
        </Eyebrow>

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
              className="input-field w-full rounded-xl px-4 py-3 text-sm resize-none"
            />
            <div className="flex items-center justify-between">
              <p
                className="text-xs"
                style={{ color: "var(--outline-variant)" }}
              >
                ⌘↵ to submit
              </p>
              <Button onClick={submitAnswer} disabled={!userAnswer.trim() || submitting}>
                {submitting ? "Checking…" : "Submit"}
              </Button>
            </div>
          </div>
        )}

        {/* Feedback panel */}
        {feedback && (
          <div
            className="rounded-2xl p-5 space-y-4"
            style={{
              background: feedback.is_correct ? "rgba(239,254,229,0.7)" : "rgba(254,242,242,0.7)",
              border: `1px solid ${feedback.is_correct ? "#86efac" : "#fca5a5"}`,
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
              <Button iconRight="arrow_forward" onClick={nextQuestion}>
                {isLast ? "See Results" : "Next Question"}
              </Button>
            </div>
          </div>
        )}
      </Card>

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
    </Page>
  );
}
