import { useState, useEffect } from "react";
import CreditIcon from "../components/CreditIcon";
import LevelPicker from "../components/LevelPicker.jsx";
import { useApp } from "../context/AppContext.jsx";
import { levelLabel, splitLevel } from "../utils.jsx";
import {
  Page,
  PageHeader,
  Card,
  Button,
  IconTile,
  ProgressBar,
  SectionTitle,
} from "../components/ui/index.jsx";

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
    saveLanguageLevel,
    setUserLanguages,
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
  const [chosenLevel, setChosenLevel] = useState(null); // user-adjusted level
  const [savedLevel, setSavedLevel] = useState(null); // last level persisted
  const [savingLevel, setSavingLevel] = useState(false);

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
        const suggested = data.suggested_level || data.determined_level;
        setResults(data);
        setChosenLevel(suggested);
        setSavedLevel(suggested); // backend already persisted the suggestion
        setUserLanguages((langs) =>
          langs.map((l) =>
            l.id === currentLanguageId ? { ...l, level: suggested } : l,
          ),
        );
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

  async function saveChosenLevel() {
    if (!chosenLevel || !currentLanguageId) return;
    setSavingLevel(true);
    try {
      const saved = await saveLanguageLevel(currentLanguageId, chosenLevel);
      setSavedLevel(saved);
    } catch (e) {
      alert(e.message || "Failed to save level");
    } finally {
      setSavingLevel(false);
    }
  }

  async function generateContent() {
    if (!sessionId) return;
    // Make sure any adjusted level is persisted first — the backend generates
    // content from the language's saved level.
    if (chosenLevel && chosenLevel !== savedLevel) {
      showLoading("Saving your level...");
      try {
        const saved = await saveLanguageLevel(currentLanguageId, chosenLevel);
        setSavedLevel(saved);
      } catch (e) {
        hideLoading();
        alert(e.message || "Failed to save level");
        return;
      }
    }
    showLoading(
      `Generating vocabulary and grammar for ${levelLabel(chosenLevel || savedLevel)}...`,
    );
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
      <Page>
        <PageHeader
          title={`Get Started with ${currentLanguageName}`}
          subtitle="Choose how you'd like to start building your knowledge base"
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <Card variant="primary" interactive onClick={startTest} className="group">
            <IconTile icon="quiz" size="lg" tone="inverse" className="mb-6" />
            <h3 className="text-xl font-bold mb-2">Take Placement Test</h3>
            <p className="text-sm opacity-80">
              Answer questions to determine your level and get a personalised
              vocabulary list
            </p>
            <div className="mt-6 flex items-center gap-2 text-sm font-semibold">
              <span>Start test</span>
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>arrow_forward</span>
              <CreditIcon size={15} />
            </div>
          </Card>
          <Card variant="tonal" interactive onClick={() => navigate(`/${currentLanguageSlug}/notes`)} className="group">
            <IconTile icon="upload_file" size="lg" className="mb-6 !bg-white" />
            <h3 className="text-xl font-bold mb-2 text-[var(--dark)]">Upload Notes</h3>
            <p className="text-sm text-[var(--accent1)]">
              Already have study materials? Upload them to extract vocabulary
              and grammar
            </p>
            <div className="mt-6 flex items-center gap-2 text-sm font-semibold text-[var(--primary)]">
              <span>Upload files</span>
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>arrow_forward</span>
            </div>
          </Card>
        </div>
      </Page>
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
      <Page>
        <PageHeader
          eyebrow={`Question ${questionIndex + 1}`}
          title="Placement Test"
          subtitle={`Level ${question.level || "—"} · ${questionsAtLevel}/${questionsPerLevel} at this level`}
          className="!mb-6"
        />
        <div className="mb-8">
          <ProgressBar value={progress} />
          <p className="text-xs text-[var(--accent1)] mt-2">
            The test adapts to your level — it ends early once your level is
            found, and goes longer if you're doing well.
          </p>
        </div>

        <div>
          <Card className="mb-6">
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
          </Card>

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
            <Button
              variant="secondary"
              size="lg"
              icon="help"
              onClick={() => submitAnswer("__dont_know__")}
              disabled={waitingNext}
            >
              Don't know
            </Button>
            <Button
              size="lg"
              className="flex-1"
              onClick={() => submitAnswer()}
              disabled={waitingNext || !(selectedAnswer || textAnswer.trim())}
            >
              {waitingNext ? "Processing..." : "Submit Answer"}
              {!waitingNext && <CreditIcon />}
            </Button>
          </div>
        </div>
      </Page>
    );
  }

  // ---- Results View ----
  if (view === "results" && results) {
    const suggested = results.suggested_level || results.determined_level;
    const current = chosenLevel || suggested;
    const { cefr } = splitLevel(current);
    const adjusted = current !== suggested;
    const levelSaved = current === savedLevel;
    return (
      <Page>
        <PageHeader
          eyebrow="Session Complete"
          title="Test Complete!"
          subtitle={`Your ${currentLanguageName} placement result`}
        />

        <div>
          <Card variant="primary" className="mb-6">
            <div className="flex flex-col md:flex-row md:items-start gap-8">
              <div className="flex items-center gap-6 shrink-0">
                <div className="text-7xl font-extrabold tracking-tight">{cefr}</div>
                <div>
                  <p className="text-lg font-bold">{levelLabel(chosenLevel || suggested)}</p>
                  <p className="text-sm mt-1 opacity-80">
                    {adjusted
                      ? `We suggested ${levelLabel(suggested)} — you've adjusted it.`
                      : "Our suggestion, based on your answers"}
                  </p>
                </div>
              </div>
              <div className="flex-1 md:border-l md:border-white/20 md:pl-8">
                <p className="text-sm font-semibold mb-3 opacity-90">
                  Not quite right? Pick the level that feels like you.
                </p>
                <LevelPicker
                  inverse
                  value={chosenLevel || suggested}
                  onChange={setChosenLevel}
                />
                <div className="mt-4 flex items-center gap-3">
                  <Button
                    variant="inverse"
                    size="sm"
                    icon={levelSaved ? "check" : "save"}
                    disabled={savingLevel || levelSaved}
                    onClick={saveChosenLevel}
                  >
                    {levelSaved ? "Level saved" : savingLevel ? "Saving…" : "Save level"}
                  </Button>
                  {adjusted && (
                    <button
                      className="text-xs underline opacity-80"
                      onClick={() => setChosenLevel(suggested)}
                    >
                      Reset to suggestion
                    </button>
                  )}
                </div>
              </div>
            </div>
          </Card>

          {results.breakdown && (
            <Card variant="tonal" padding="md" className="mb-6">
              <SectionTitle>Score Breakdown</SectionTitle>
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
            </Card>
          )}

          <div className="flex gap-3">
            <Button size="lg" icon="auto_fix_high" className="flex-1" onClick={generateContent}>
              Generate Vocabulary for {levelLabel(current)}
              <CreditIcon />
            </Button>
            <Button size="lg" variant="secondary" onClick={() => navigate(`/${currentLanguageSlug}/`)}>
              Skip
            </Button>
          </div>
        </div>
      </Page>
    );
  }

  // ---- Review View ----
  if (view === "review") {
    const saveButtons = (
      <div className="flex gap-3">
        <Button size="lg" icon="save" onClick={saveContent}>
          Save to Knowledge Base
        </Button>
        <Button size="lg" variant="secondary" onClick={() => navigate(`/${currentLanguageSlug}/vocabulary`)}>
          Skip
        </Button>
      </div>
    );

    return (
      <Page>
        <PageHeader
          title="Review Your Vocabulary"
          subtitle="Edit or remove items before saving to your knowledge base"
          actions={saveButtons}
        />

        {/* Vocabulary review table */}
        {reviewVocab.length > 0 && (
          <Card padding="md" className="mb-6">
            <SectionTitle>Vocabulary ({reviewVocab.length})</SectionTitle>
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
          </Card>
        )}

        {/* Grammar review */}
        {reviewGrammar.length > 0 && (
          <Card padding="md" className="mb-6">
            <SectionTitle>Grammar ({reviewGrammar.length})</SectionTitle>
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
          </Card>
        )}

        <div className="flex justify-end">{saveButtons}</div>
      </Page>
    );
  }

  return null;
}
