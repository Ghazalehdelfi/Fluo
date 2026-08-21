import { useState, useEffect } from "react";
import CreditIcon from "../components/CreditIcon";
import { useApp } from "../context/AppContext.jsx";

export default function PlacementPage() {
  const {
    currentLanguageId,
    currentLanguageName,
    currentLanguageSlug,
    apiFetch,
    navigate,
    showLoading,
    hideLoading,
    invalidateCache,
  } = useApp();
  const [view, setView] = useState("choice"); // 'choice' | 'test' | 'results' | 'review'

  // Placement test state
  const [sessionId, setSessionId] = useState(null);
  const [question, setQuestion] = useState(null);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [levelIndex, setLevelIndex] = useState(0);
  const [questionsAtLevel, setQuestionsAtLevel] = useState(1);
  const [questionsPerLevel, setQuestionsPerLevel] = useState(3);
  const [totalLevels, setTotalLevels] = useState(6);
  const [selectedAnswer, setSelectedAnswer] = useState("");
  const [textAnswer, setTextAnswer] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [feedbackCorrect, setFeedbackCorrect] = useState(null);
  const [waitingNext, setWaitingNext] = useState(false);
  const [showRomanization, setShowRomanization] = useState(false);

  // Results state
  const [results, setResults] = useState(null);

  // Review state
  const [reviewVocab, setReviewVocab] = useState([]);
  const [reviewGrammar, setReviewGrammar] = useState([]);

  async function startTest() {
    showLoading("Starting placement test...");
    try {
      const resp = await apiFetch(
        `/api/placement-test/start/${currentLanguageId}`,
        { method: "POST" },
      );
      if (!resp.ok) {
        alert("Failed to start test");
        hideLoading();
        return;
      }
      const data = await resp.json();
      setSessionId(data.session_id);
      setQuestion(data.question);
      setQuestionIndex(0);
      setLevelIndex(data.level_index ?? 0);
      setQuestionsAtLevel(data.questions_at_level ?? 1);
      setQuestionsPerLevel(data.questions_per_level ?? 3);
      setTotalLevels(data.total_levels ?? 6);
      setFeedback(null);
      setFeedbackCorrect(null);
      setSelectedAnswer("");
      setTextAnswer("");
      setWaitingNext(false);
      setShowRomanization(false);
      setView("test");
    } catch (e) {
      console.error(e);
      alert("Error starting test");
    } finally {
      hideLoading();
    }
  }

  async function submitAnswer(overrideAnswer = null) {
    const isDontKnow = overrideAnswer === "__dont_know__";
    const answer = overrideAnswer || selectedAnswer || textAnswer;
    if (!answer.trim() || !sessionId) return;
    setWaitingNext(true);
    try {
      const resp = await apiFetch(`/api/placement-test/${sessionId}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer }),
      });
      if (!resp.ok) {
        setWaitingNext(false);
        return;
      }
      const data = await resp.json();
      if (!isDontKnow && data.correct !== undefined) {
        setFeedback(
          data.feedback || (data.correct ? "Correct!" : "Not quite."),
        );
        setFeedbackCorrect(data.correct);
      }
      const delay = isDontKnow ? 0 : 1200;
      if (data.completed || data.finished) {
        setResults(data);
        setView("results");
      } else if (data.question || data.next_question) {
        setTimeout(() => {
          setQuestion(data.question || data.next_question);
          setQuestionIndex((qi) => qi + 1);
          if (data.level_index !== undefined) setLevelIndex(data.level_index);
          if (data.questions_at_level !== undefined)
            setQuestionsAtLevel(data.questions_at_level);
          if (data.questions_per_level !== undefined)
            setQuestionsPerLevel(data.questions_per_level);
          if (data.total_levels !== undefined)
            setTotalLevels(data.total_levels);
          setSelectedAnswer("");
          setTextAnswer("");
          setFeedback(null);
          setFeedbackCorrect(null);
          setWaitingNext(false);
          setShowRomanization(false);
        }, delay);
      } else {
        setWaitingNext(false);
      }
    } catch (e) {
      console.error(e);
      setWaitingNext(false);
    }
  }

  async function generateContent() {
    if (!sessionId) return;
    showLoading("Generating vocabulary and grammar for your level...");
    try {
      const resp = await apiFetch(
        `/api/placement-test/${sessionId}/generate-content`,
        { method: "POST" },
      );
      if (!resp.ok) {
        hideLoading();
        return;
      }
      const data = await resp.json();
      setReviewVocab(
        (data.vocabulary || []).map((v) => ({ ...v, _edit: false })),
      );
      setReviewGrammar(
        (data.grammar || []).map((g) => ({ ...g, _edit: false })),
      );
      setView("review");
    } catch (e) {
      console.error(e);
    } finally {
      hideLoading();
    }
  }

  async function saveContent() {
    if (!sessionId) return;
    showLoading("Saving to your knowledge base...");
    try {
      const resp = await apiFetch(
        `/api/placement-test/${sessionId}/save-content`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            vocabulary: reviewVocab,
            grammar: reviewGrammar,
          }),
        },
      );
      hideLoading();
      if (!resp.ok) {
        alert("Failed to save");
        return;
      }
      // Clear cached vocab/stats/grammar so the new words show up immediately
      invalidateCache(currentLanguageId);
      navigate(`/${currentLanguageSlug}/vocabulary`);
    } catch (e) {
      console.error(e);
      hideLoading();
    }
  }

  function updateReviewVocab(i, field, val) {
    setReviewVocab((v) =>
      v.map((item, idx) => (idx === i ? { ...item, [field]: val } : item)),
    );
  }

  function removeReviewVocab(i) {
    setReviewVocab((v) => v.filter((_, idx) => idx !== i));
  }
  function removeReviewGrammar(i) {
    setReviewGrammar((g) => g.filter((_, idx) => idx !== i));
  }

  function updateReviewGrammar(i, field, val) {
    setReviewGrammar((g) =>
      g.map((item, idx) => (idx === i ? { ...item, [field]: val } : item)),
    );
  }

  // ---- Choice View ----
  if (view === "choice") {
    return (
      <div>
        <header className="mb-12">
          <h2
            className="text-4xl font-bold tracking-tight"
            style={{ color: "var(--dark)" }}
          >
            Get Started with {currentLanguageName}
          </h2>
          <p className="text-[#596060] mt-2 text-lg">
            Choose how you'd like to start building your knowledge base
          </p>
        </header>
        <div className="grid grid-cols-2 gap-6 max-w-3xl">
          <div
            onClick={startTest}
            className="rounded-3xl p-10 cursor-pointer transition-all hover:shadow-lg group"
            style={{
              background: "var(--primary)",
              color: "var(--on-primary)",
              boxShadow: "0 8px 32px rgba(67,101,101,0.15)",
            }}
          >
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center mb-8"
              style={{ background: "rgba(255,255,255,0.15)" }}
            >
              <span
                className="material-symbols-outlined"
                style={{ color: "var(--on-primary)", fontSize: 30 }}
              >
                quiz
              </span>
            </div>
            <h3 className="text-2xl font-bold mb-3">Take Placement Test</h3>
            <p className="text-sm" style={{ opacity: 0.8 }}>
              Answer questions to determine your level and get a personalised
              vocabulary list
            </p>
            <div className="mt-8 flex items-center gap-2 text-sm font-medium">
              <span>Start test</span>
              <span
                className="material-symbols-outlined"
                style={{ fontSize: 18 }}
              >
                arrow_forward
              </span>
              <span
                className="material-symbols-outlined"
                style={{ fontSize: 15, opacity: 0.75 }}
                title="This action uses AI and will consume credits"
              >
                toll
              </span>
            </div>
          </div>
          <div
            onClick={() => navigate(`/${currentLanguageSlug}/notes`)}
            className="rounded-3xl p-10 cursor-pointer transition-all hover:shadow-md group"
            style={{
              background: "var(--surface-container-low)",
              boxShadow: "0 4px 16px rgba(45,52,51,0.04)",
            }}
          >
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center mb-8"
              style={{ background: "var(--white)" }}
            >
              <span
                className="material-symbols-outlined"
                style={{ color: "var(--primary)", fontSize: 30 }}
              >
                upload_file
              </span>
            </div>
            <h3
              className="text-2xl font-bold mb-3"
              style={{ color: "var(--dark)" }}
            >
              Upload Notes
            </h3>
            <p className="text-sm text-[#596060]">
              Already have study materials? Upload them to extract vocabulary
              and grammar
            </p>
            <div
              className="mt-8 flex items-center gap-2 text-sm font-medium"
              style={{ color: "var(--primary)" }}
            >
              <span>Upload files</span>
              <span
                className="material-symbols-outlined"
                style={{ fontSize: 18 }}
              >
                arrow_forward
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---- Test View ----
  if (view === "test" && question) {
    const progress = Math.min(
      100,
      Math.round(
        ((levelIndex + questionsAtLevel / questionsPerLevel) / totalLevels) *
          100,
      ),
    );
    const isMultipleChoice =
      question.type === "multiple_choice" ||
      (question.options && question.options.length > 0);
    const questionText = question.text || question.question || "";
    const hasRomanization =
      question.romanization &&
      question.romanization.trim() !== questionText.trim();

    return (
      <div>
        <header className="mb-10">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-bold" style={{ color: "var(--dark)" }}>
              Placement Test
            </h2>
            <div className="text-right">
              <span
                className="text-sm font-medium"
                style={{ color: "var(--dark)" }}
              >
                Question {questionIndex + 1}
              </span>
              <p className="text-xs text-[#596060]">
                Level {question.level || "—"} · {questionsAtLevel}/
                {questionsPerLevel} at this level
              </p>
            </div>
          </div>
          <div
            className="h-2 rounded-full overflow-hidden"
            style={{ background: "var(--surface-container-high)" }}
          >
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${progress}%`, background: "var(--primary)" }}
            />
          </div>
          <p className="text-xs text-[#596060] mt-2">
            The test adapts to your level — it ends early once your level is
            found, and goes longer if you're doing well.
          </p>
        </header>

        <div className="max-w-2xl">
          <div
            className="rounded-2xl p-8 mb-6"
            style={{
              background: "var(--white)",
              boxShadow: "0 8px 32px rgba(45,52,51,0.06)",
            }}
          >
            <div className="mb-2">
              {question.topic && (
                <span className="text-xs font-bold uppercase tracking-widest text-[#596060]">
                  {question.topic}
                </span>
              )}
            </div>
            <p
              className="text-xl font-semibold"
              style={{ color: "var(--dark)" }}
            >
              {questionText}
            </p>
            {showRomanization && hasRomanization && (
              <p
                className="mt-3 text-sm font-medium"
                style={{ color: "var(--primary)", direction: "ltr" }}
              >
                {question.romanization}
              </p>
            )}
            {hasRomanization && (
              <button
                onClick={() => setShowRomanization((r) => !r)}
                className="mt-4 text-xs px-3 py-1 rounded-full transition-colors"
                style={{
                  background: showRomanization
                    ? "var(--primary)"
                    : "var(--surface-container-low)",
                  color: showRomanization
                    ? "var(--on-primary)"
                    : "var(--accent1)",
                }}
              >
                {showRomanization ? "Hide Latin" : "Latin"}
              </button>
            )}
          </div>

          {feedback && (
            <div
              className={`rounded-xl px-5 py-4 mb-6 flex items-center gap-3 text-sm font-medium`}
              style={{
                background: feedbackCorrect
                  ? "rgba(239,254,229,0.7)"
                  : "rgba(254,242,242,0.7)",
                color: feedbackCorrect ? "#166534" : "#991b1b",
                border: `1px solid ${feedbackCorrect ? "#86efac" : "#fca5a5"}`,
              }}
            >
              <span
                className="material-symbols-outlined"
                style={{ fontSize: 18, fontVariationSettings: "'FILL' 1" }}
              >
                {feedbackCorrect ? "check_circle" : "cancel"}
              </span>
              {feedback}
            </div>
          )}

          {isMultipleChoice ? (
            <div className="space-y-3">
              {question.options.map((opt, i) => (
                <button
                  key={i}
                  onClick={() => !waitingNext && setSelectedAnswer(opt)}
                  className={`w-full text-left px-6 py-4 rounded-xl transition-all text-sm font-medium`}
                  style={{
                    background:
                      selectedAnswer === opt
                        ? "var(--primary)"
                        : "var(--surface-container-low)",
                    color:
                      selectedAnswer === opt
                        ? "var(--on-primary)"
                        : "var(--dark)",
                    outline: selectedAnswer === opt ? "none" : "",
                  }}
                >
                  {opt}
                  {showRomanization &&
                    question.option_romanizations?.[i] &&
                    question.option_romanizations[i].trim() !==
                      String(opt).trim() && (
                      <span
                        className="block mt-1 text-xs font-normal"
                        style={{ opacity: 0.8, direction: "ltr" }}
                      >
                        {question.option_romanizations[i]}
                      </span>
                    )}
                </button>
              ))}
            </div>
          ) : (
            <input
              className="input-field w-full px-5 py-4 rounded-xl text-sm"
              placeholder="Type your answer..."
              value={textAnswer}
              onChange={(e) => !waitingNext && setTextAnswer(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitAnswer()}
            />
          )}

          <div className="mt-6 flex gap-3">
            <button
              onClick={() => submitAnswer("__dont_know__")}
              disabled={waitingNext}
              className="btn-secondary flex-none px-6 py-4 rounded-xl font-medium disabled:opacity-40 flex items-center gap-2"
            >
              <span
                className="material-symbols-outlined"
                style={{ fontSize: 18 }}
              >
                help
              </span>
              Don't know
            </button>
            <button
              onClick={() => submitAnswer()}
              disabled={waitingNext || !(selectedAnswer || textAnswer.trim())}
              className="btn-primary flex-1 py-4 rounded-xl font-semibold disabled:opacity-40 flex items-center justify-center gap-2"
            >
              {waitingNext ? "Processing..." : "Submit Answer"}
              {!waitingNext && <CreditIcon />}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ---- Results View ----
  if (view === "results" && results) {
    const level = results.level || results.determined_level;
    return (
      <div>
        <header className="mb-10">
          <h2
            className="text-4xl font-bold tracking-tight"
            style={{ color: "var(--dark)" }}
          >
            Test Complete!
          </h2>
          <p className="text-[#596060] mt-2">
            Your {currentLanguageName} placement result
          </p>
        </header>

        <div className="max-w-2xl">
          <div
            className="rounded-3xl p-10 mb-8 flex items-center gap-8"
            style={{
              background: "var(--primary)",
              color: "var(--on-primary)",
              boxShadow: "0 8px 32px rgba(67,101,101,0.15)",
            }}
          >
            <div className="text-8xl font-extrabold">{level || "—"}</div>
            <div>
              <p className="text-lg font-bold">Determined Level</p>
              <p className="text-sm mt-1" style={{ opacity: 0.8 }}>
                Based on your performance
              </p>
            </div>
          </div>

          {results.breakdown && (
            <div
              className="rounded-2xl p-6 mb-8"
              style={{ background: "var(--surface-container-low)" }}
            >
              <h3 className="font-bold mb-4" style={{ color: "var(--dark)" }}>
                Score Breakdown
              </h3>
              <table className="w-full text-sm">
                <tbody>
                  {Object.entries(results.breakdown).map(([k, v]) => (
                    <tr
                      key={k}
                      className="border-b"
                      style={{ borderColor: "var(--outline-variant)" }}
                    >
                      <td
                        className="py-2 capitalize"
                        style={{ color: "var(--accent1)" }}
                      >
                        {k.replace(/_/g, " ")}
                      </td>
                      <td
                        className="py-2 font-semibold text-right"
                        style={{ color: "var(--dark)" }}
                      >
                        {v}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={generateContent}
              className="btn-primary flex-1 py-4 rounded-xl font-semibold flex items-center gap-2"
            >
              <span className="material-symbols-outlined">auto_fix_high</span>
              Generate Vocabulary for My Level
              <CreditIcon />
            </button>
            <button
              onClick={() => navigate(`/${currentLanguageSlug}/`)}
              className="btn-secondary px-6 py-4 rounded-xl font-medium"
            >
              Skip
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ---- Review View ----
  if (view === "review") {
    const saveButtons = (
      <div className="flex gap-3">
        <button
          onClick={saveContent}
          className="btn-primary px-8 py-4 rounded-xl font-semibold flex items-center gap-2"
        >
          <span className="material-symbols-outlined">save</span>
          Save to Knowledge Base
        </button>
        <button
          onClick={() => navigate(`/${currentLanguageSlug}/vocabulary`)}
          className="btn-secondary px-6 py-4 rounded-xl font-medium"
        >
          Skip
        </button>
      </div>
    );

    return (
      <div>
        <header className="mb-6">
          <h2
            className="text-4xl font-bold tracking-tight"
            style={{ color: "var(--dark)" }}
          >
            Review Your Vocabulary
          </h2>
          <p className="text-[#596060] mt-2">
            Edit or remove items before saving to your knowledge base
          </p>
        </header>

        <div className="mb-8">{saveButtons}</div>

        {/* Vocabulary review table */}
        {reviewVocab.length > 0 && (
          <div
            className="rounded-2xl p-6 mb-8"
            style={{
              background: "var(--white)",
              boxShadow: "0 4px 16px rgba(45,52,51,0.04)",
            }}
          >
            <h3 className="font-bold mb-4" style={{ color: "var(--dark)" }}>
              Vocabulary ({reviewVocab.length})
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr
                    className="text-xs uppercase tracking-widest"
                    style={{ color: "var(--accent1)" }}
                  >
                    <th className="text-left pb-3 pr-4">Word</th>
                    <th className="text-left pb-3 pr-4">Translation</th>
                    <th className="text-left pb-3 pr-4">Example</th>
                    <th className="pb-3" />
                  </tr>
                </thead>
                <tbody className="space-y-2">
                  {reviewVocab.map((v, i) => (
                    <tr
                      key={i}
                      className="border-t"
                      style={{ borderColor: "var(--surface-container-low)" }}
                    >
                      <td className="py-3 pr-4">
                        <input
                          className="input-field px-3 py-2 rounded-lg text-sm w-full"
                          value={v.target_word || ""}
                          onChange={(e) =>
                            updateReviewVocab(i, "target_word", e.target.value)
                          }
                        />
                      </td>
                      <td className="py-3 pr-4">
                        <input
                          className="input-field px-3 py-2 rounded-lg text-sm w-full"
                          value={v.native_translation || ""}
                          onChange={(e) =>
                            updateReviewVocab(
                              i,
                              "native_translation",
                              e.target.value,
                            )
                          }
                        />
                      </td>
                      <td className="py-3 pr-4">
                        <input
                          className="input-field px-3 py-2 rounded-lg text-sm w-full"
                          value={v.example_sentence || ""}
                          onChange={(e) =>
                            updateReviewVocab(
                              i,
                              "example_sentence",
                              e.target.value,
                            )
                          }
                        />
                      </td>
                      <td className="py-3">
                        <button
                          onClick={() => removeReviewVocab(i)}
                          className="p-1 transition-colors"
                          style={{ color: "var(--outline-variant)" }}
                          onMouseEnter={(e) =>
                            (e.currentTarget.style.color = "#a83836")
                          }
                          onMouseLeave={(e) =>
                            (e.currentTarget.style.color =
                              "var(--outline-variant)")
                          }
                        >
                          <span
                            className="material-symbols-outlined"
                            style={{ fontSize: 18 }}
                          >
                            delete
                          </span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Grammar review */}
        {reviewGrammar.length > 0 && (
          <div
            className="rounded-2xl p-6 mb-8"
            style={{
              background: "var(--white)",
              boxShadow: "0 4px 16px rgba(45,52,51,0.04)",
            }}
          >
            <h3 className="font-bold mb-4" style={{ color: "var(--dark)" }}>
              Grammar ({reviewGrammar.length})
            </h3>
            <div className="space-y-4">
              {reviewGrammar.map((g, i) => (
                <div
                  key={i}
                  className="flex gap-3 items-start p-4 rounded-xl"
                  style={{ background: "var(--surface-container-low)" }}
                >
                  <div className="flex-1 space-y-2">
                    <input
                      className="input-field px-3 py-2 rounded-lg text-sm w-full font-medium"
                      value={g.concept_name || ""}
                      placeholder="Concept name"
                      onChange={(e) =>
                        updateReviewGrammar(i, "concept_name", e.target.value)
                      }
                    />
                    <textarea
                      className="input-field px-3 py-2 rounded-lg text-sm w-full resize-none"
                      rows={2}
                      value={g.description || ""}
                      placeholder="Description"
                      onChange={(e) =>
                        updateReviewGrammar(i, "description", e.target.value)
                      }
                    />
                  </div>
                  <button
                    onClick={() => removeReviewGrammar(i)}
                    className="p-1 transition-colors mt-2 shrink-0"
                    style={{ color: "var(--outline-variant)" }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.color = "#a83836")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.color = "var(--outline-variant)")
                    }
                  >
                    <span
                      className="material-symbols-outlined"
                      style={{ fontSize: 18 }}
                    >
                      delete
                    </span>
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {saveButtons}
      </div>
    );
  }

  return null;
}
