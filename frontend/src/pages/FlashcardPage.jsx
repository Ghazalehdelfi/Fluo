import { useState, useEffect, useRef, useCallback } from "react";
import { useApp } from "../context/AppContext";
import { speakText } from "../utils.jsx";

export default function FlashcardPage() {
  const {
    currentLanguageId,
    currentLanguageName,
    nativeLanguage,
    apiFetch,
    navigate,
    currentLanguageSlug,
    fetchVocabulary,
    invalidateCache,
  } = useApp();
  const [view, setView] = useState("setup"); // 'setup' | 'active' | 'results'

  // Setup state
  const [direction, setDirection] = useState("target");
  const [fluencyFilter, setFluencyFilter] = useState("all");
  const [wordCount, setWordCount] = useState(0);

  // Active session state
  const [deck, setDeck] = useState([]);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [correctCount, setCorrectCount] = useState(0);
  const [wrongCount, setWrongCount] = useState(0);
  const [streak, setStreak] = useState(0);
  const [results, setResults] = useState([]);

  const innerRef = useRef(null);

  // Load vocab count on filter change
  useEffect(() => {
    if (currentLanguageId) {
      fetchVocabulary(currentLanguageId)
        .then((vocab) => {
          const filtered = filterVocab(vocab, fluencyFilter);
          setWordCount(filtered.length);
        })
        .catch(() => {});
    }
  }, [currentLanguageId, fluencyFilter]);

  function filterVocab(vocab, filter) {
    if (filter === "all") return vocab;
    return vocab.filter((v) => v.fluency_level === filter);
  }

  async function beginFlashcards() {
    const vocab = await fetchVocabulary(currentLanguageId);
    let d = filterVocab(vocab, fluencyFilter);
    if (d.length === 0) {
      alert("No vocabulary words match your filter. Upload some notes first!");
      return;
    }
    // Shuffle
    for (let i = d.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [d[i], d[j]] = [d[j], d[i]];
    }
    setDeck(d);
    setIndex(0);
    setFlipped(false);
    setCorrectCount(0);
    setWrongCount(0);
    setStreak(0);
    setResults([]);
    setView("active");
  }

  function flipCard() {
    setFlipped((f) => !f);
  }

  async function answer(correct) {
    const card = deck[index];
    const newResult = {
      vocab_id: card.id,
      word: card.target_word,
      translation: card.native_translation,
      correct,
      fluency: card.fluency_level,
    };
    if (correct) {
      setCorrectCount((c) => c + 1);
      setStreak((s) => s + 1);
    } else {
      setWrongCount((w) => w + 1);
      setStreak(0);
    }

    try {
      const resp = await apiFetch(`/api/flashcard-result/${card.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ correct }),
      });
      if (resp.ok) {
        const updated = await resp.json();
        newResult.new_fluency = updated.fluency_level;
        deck[index].fluency_level = updated.fluency_level;
        // Fluency changed — invalidate vocab + stats cache for this language
        invalidateCache(currentLanguageId, "vocab", "stats", "dashboard");
      }
    } catch {}

    setResults((r) => [...r, newResult]);
    const next = index + 1;
    if (next < deck.length) {
      setIndex(next);
      setFlipped(false);
    } else {
      setView("results");
    }
  }

  function skipCard() {
    const next = index + 1;
    if (next < deck.length) {
      setIndex(next);
      setFlipped(false);
    } else {
      setView("results");
    }
  }

  function endSession() {
    if (results.length > 0) setView("results");
    else resetSession();
  }

  function resetSession() {
    setView("setup");
    setFlipped(false);
    setCorrectCount(0);
    setWrongCount(0);
    setStreak(0);
    setResults([]);
  }

  // Keyboard shortcuts
  useEffect(() => {
    function onKeyDown(e) {
      if (view !== "active") return;
      if (e.code === "Space") {
        e.preventDefault();
        flipCard();
      } else if (e.code === "ArrowRight" && flipped) answer(true);
      else if (e.code === "ArrowLeft" && flipped) answer(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [view, flipped, index]);

  // Setup view
  if (view === "setup") {
    return (
      <div>
        <div className="mb-10">
          <h1
            className="text-4xl font-extrabold tracking-tight"
            style={{ color: "var(--dark)" }}
          >
            {currentLanguageName} Flashcards
          </h1>
          <p className="mt-2 text-[#596060]">
            Review your vocabulary with flashcards
          </p>
        </div>
        <div className="card rounded-2xl p-8 max-w-lg mx-auto">
          <div className="space-y-6">
            <div>
              <label
                className="block text-sm font-medium mb-3"
                style={{ color: "var(--dark)" }}
              >
                Show me the word in
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => setDirection("target")}
                  className={`${direction === "target" ? "btn-primary" : "btn-secondary"} px-4 py-3 rounded-xl text-sm font-medium`}
                >
                  {currentLanguageName}
                </button>
                <button
                  onClick={() => setDirection("native")}
                  className={`${direction === "native" ? "btn-primary" : "btn-secondary"} px-4 py-3 rounded-xl text-sm font-medium`}
                >
                  {nativeLanguage}
                </button>
              </div>
            </div>
            <div>
              <label
                className="block text-sm font-medium mb-3"
                style={{ color: "var(--dark)" }}
              >
                Filter by fluency
              </label>
              <div className="flex gap-2">
                {["all", "low", "medium", "high"].map((level) => (
                  <button
                    key={level}
                    onClick={() => setFluencyFilter(level)}
                    className={`${fluencyFilter === level ? "btn-primary" : "btn-secondary"} flex-1 px-4 py-3 rounded-xl text-sm font-medium capitalize`}
                  >
                    {level === "all"
                      ? "All"
                      : level.charAt(0).toUpperCase() + level.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            <div
              className="text-sm text-center"
              style={{ color: "var(--accent1)" }}
            >
              {wordCount} words available
            </div>
            <button
              onClick={beginFlashcards}
              disabled={wordCount === 0}
              className="btn-primary w-full px-4 py-3 rounded-xl text-sm font-medium disabled:opacity-40"
            >
              Start Flashcards
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Active session
  if (view === "active" && deck.length > 0) {
    const card = deck[index];
    const total = deck.length;
    const num = index + 1;
    const frontWord =
      direction === "target" ? card.target_word : card.native_translation;
    const backWord =
      direction === "target" ? card.native_translation : card.target_word;
    const badge = (
      <span
        className={`fluency-${card.fluency_level} px-2.5 py-1 rounded-full text-xs font-medium`}
      >
        {card.fluency_level}
      </span>
    );
    const segments = Math.min(total, 10);
    const filled = Math.ceil((num / total) * segments);

    return (
      <div>
        <header className="flex justify-between items-end mb-12">
          <div className="space-y-2">
            <span className="text-xs font-bold tracking-[0.1em] uppercase text-[#596060]">
              Active Session
            </span>
            <h2
              className="text-4xl font-extrabold tracking-tight"
              style={{ color: "var(--dark)" }}
            >
              Flashcards
            </h2>
            <div className="flex items-center gap-2 mt-4">
              <span
                className="text-sm font-medium"
                style={{ color: "var(--primary)" }}
              >
                Card {num} of {total}
              </span>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <div className="flex gap-1 w-48 h-1.5">
              {Array.from({ length: segments }, (_, i) => (
                <div
                  key={i}
                  className="flex-1 rounded-full"
                  style={{
                    height: 6,
                    background:
                      i < filled
                        ? "var(--primary)"
                        : "var(--surface-container-high)",
                  }}
                />
              ))}
            </div>
            <div className="flex items-center gap-4">
              <span className="text-xs font-bold uppercase tracking-widest text-[#596060]">
                Progress
              </span>
              <button
                onClick={endSession}
                className="btn-secondary px-4 py-2 rounded-xl text-xs font-medium"
              >
                End
              </button>
            </div>
          </div>
        </header>

        <section className="flex flex-col items-center w-full">
          {/* Mobile stats strip */}
          <div className="lg:hidden w-full flex gap-3 mb-4">
            <div
              className="flex-1 rounded-2xl p-4 flex items-center gap-3"
              style={{ background: "var(--surface-container-low)" }}
            >
              <span
                className="material-symbols-outlined"
                style={{ color: "var(--primary)", fontSize: 20 }}
              >
                check_circle
              </span>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-[#596060]">
                  Correct
                </p>
                <p
                  className="text-xl font-extrabold"
                  style={{ color: "var(--dark)" }}
                >
                  {correctCount}
                </p>
              </div>
            </div>
            <div
              className="flex-1 rounded-2xl p-4 flex items-center gap-3"
              style={{ background: "var(--surface-container-low)" }}
            >
              <span
                className="material-symbols-outlined"
                style={{ color: "#a83836", fontSize: 20 }}
              >
                close
              </span>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-[#596060]">
                  Wrong
                </p>
                <p
                  className="text-xl font-extrabold"
                  style={{ color: "var(--dark)" }}
                >
                  {wrongCount}
                </p>
              </div>
            </div>
            <div
              className="flex-1 rounded-2xl p-4 flex items-center gap-3"
              style={{
                background: "var(--primary)",
                color: "var(--on-primary)",
              }}
            >
              <span
                className="material-symbols-outlined"
                style={{ fontSize: 20 }}
              >
                bolt
              </span>
              <div>
                <p
                  className="text-[10px] font-bold uppercase tracking-widest"
                  style={{ opacity: 0.8 }}
                >
                  Streak
                </p>
                <p className="text-xl font-extrabold">{streak}</p>
              </div>
            </div>
          </div>
          <div
            className="grid grid-cols-1 lg:grid-cols-12 gap-6 w-full"
            style={{ height: 480 }}
          >
            {/* Flashcard */}
            <div
              className="lg:col-span-8 flashcard-container"
              onClick={flipCard}
            >
              <div className="flashcard-inner">
                <div className="flashcard-front">
                  {!flipped ? (
                    <>
                      <div
                        style={{
                          position: "absolute",
                          top: "-6rem",
                          right: "-6rem",
                          width: "16rem",
                          height: "16rem",
                          background: "var(--tertiary-container)",
                          borderRadius: "50%",
                          opacity: 0.15,
                        }}
                      />
                      <div className="flashcard-counter">
                        {num} / {total}
                      </div>
                      <div className="flashcard-fluency">{badge}</div>
                      <div
                        style={{
                          position: "relative",
                          zIndex: 10,
                          textAlign: "center",
                        }}
                      >
                        <div className="flashcard-word">{frontWord}</div>
                        <button
                          className="fc-sound-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            speakText(frontWord);
                          }}
                          title="Listen to pronunciation"
                        >
                          <span
                            className="material-symbols-outlined"
                            style={{ fontSize: "1.5rem" }}
                          >
                            volume_up
                          </span>
                        </button>
                      </div>
                      <div
                        className="flashcard-hint"
                        style={{ position: "absolute", bottom: "2rem" }}
                      >
                        <span
                          className="material-symbols-outlined"
                          style={{ fontSize: 14 }}
                        >
                          touch_app
                        </span>
                        Tap to reveal
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="flashcard-counter">
                        {num} / {total}
                      </div>
                      <div className="flashcard-fluency">{badge}</div>
                      <div style={{ textAlign: "center" }}>
                        <div className="flashcard-word">{backWord}</div>
                        <div
                          className="text-sm mt-4"
                          style={{ color: "var(--accent1)", maxWidth: 320 }}
                        >
                          {card.example_sentence || ""}
                        </div>
                        <button
                          className="fc-sound-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            speakText(backWord);
                          }}
                          title="Listen"
                        >
                          <span
                            className="material-symbols-outlined"
                            style={{ fontSize: "1.5rem" }}
                          >
                            volume_up
                          </span>
                        </button>
                      </div>
                      <div
                        className="flashcard-hint"
                        style={{ position: "absolute", bottom: "2rem" }}
                      >
                        <span
                          className="material-symbols-outlined"
                          style={{ fontSize: 14 }}
                        >
                          flip
                        </span>
                        Tap to flip back
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Side panels */}
            <div className="hidden lg:flex lg:col-span-4 flex-col gap-6">
              <div
                className="flex-1 rounded-[1.5rem] p-8 flex flex-col justify-center"
                style={{ background: "var(--surface-container-low)" }}
              >
                <div className="flex items-center gap-4">
                  <div
                    className="p-3 rounded-xl"
                    style={{ background: "var(--white)" }}
                  >
                    <span
                      className="material-symbols-outlined"
                      style={{ color: "var(--primary)" }}
                    >
                      check_circle
                    </span>
                  </div>
                  <div>
                    <p className="text-xs font-bold uppercase tracking-widest text-[#596060]">
                      Correct
                    </p>
                    <p
                      className="text-3xl font-extrabold"
                      style={{ color: "var(--dark)" }}
                    >
                      {correctCount}
                    </p>
                  </div>
                </div>
              </div>
              <div
                className="flex-1 rounded-[1.5rem] p-8 flex flex-col justify-center"
                style={{ background: "var(--surface-container-low)" }}
              >
                <div className="flex items-center gap-4">
                  <div
                    className="p-3 rounded-xl"
                    style={{ background: "var(--white)" }}
                  >
                    <span
                      className="material-symbols-outlined"
                      style={{ color: "#a83836" }}
                    >
                      close
                    </span>
                  </div>
                  <div>
                    <p className="text-xs font-bold uppercase tracking-widest text-[#596060]">
                      Wrong
                    </p>
                    <p
                      className="text-3xl font-extrabold"
                      style={{ color: "var(--dark)" }}
                    >
                      {wrongCount}
                    </p>
                  </div>
                </div>
              </div>
              <div
                className="flex-1 rounded-[1.5rem] p-8 flex flex-col justify-center"
                style={{
                  background: "var(--primary)",
                  color: "var(--on-primary)",
                }}
              >
                <div className="flex items-center gap-4">
                  <div
                    className="p-3 rounded-xl"
                    style={{ background: "rgba(255,255,255,0.15)" }}
                  >
                    <span
                      className="material-symbols-outlined"
                      style={{ color: "var(--on-primary)" }}
                    >
                      bolt
                    </span>
                  </div>
                  <div>
                    <p
                      className="text-xs font-bold uppercase tracking-widest"
                      style={{ opacity: 0.8 }}
                    >
                      Streak
                    </p>
                    <p className="text-3xl font-extrabold">{streak}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Controls */}
          <div className="mt-10 glass-controls py-4 px-8 rounded-full flex items-center gap-10">
            <button
              onClick={() => answer(false)}
              className="flex flex-col items-center gap-1 group"
            >
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center transition-all"
                style={{
                  border: "1px solid var(--outline-variant)",
                  color: "var(--accent1)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "#fef2f2";
                  e.currentTarget.style.color = "#ef4444";
                  e.currentTarget.style.borderColor = "#ef4444";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "";
                  e.currentTarget.style.color = "var(--accent1)";
                  e.currentTarget.style.borderColor = "var(--outline-variant)";
                }}
              >
                <span className="material-symbols-outlined">close</span>
              </div>
              <span
                className="text-[10px] uppercase font-bold tracking-widest"
                style={{ color: "var(--outline-variant)" }}
              >
                Wrong
              </span>
            </button>
            <button
              onClick={() => answer(true)}
              className="flex flex-col items-center gap-1 group"
            >
              <div
                className="w-20 h-20 rounded-full flex items-center justify-center transition-all"
                style={{
                  background: "var(--primary)",
                  color: "var(--on-primary)",
                  boxShadow: "0 8px 24px rgba(67,101,101,0.15)",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.transform = "scale(1.05)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.transform = "scale(1)")
                }
              >
                <span
                  className="material-symbols-outlined"
                  style={{
                    fontSize: "2rem",
                    fontVariationSettings: "'FILL' 0, 'wght' 600",
                  }}
                >
                  check
                </span>
              </div>
              <span
                className="text-[10px] uppercase font-bold tracking-widest mt-1"
                style={{ color: "var(--primary)" }}
              >
                Correct
              </span>
            </button>
            <button
              onClick={skipCard}
              className="flex flex-col items-center gap-1 group"
            >
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center transition-all"
                style={{
                  border: "1px solid var(--outline-variant)",
                  color: "var(--accent1)",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background =
                    "var(--surface-container-high)")
                }
                onMouseLeave={(e) => (e.currentTarget.style.background = "")}
              >
                <span className="material-symbols-outlined">
                  keyboard_arrow_right
                </span>
              </div>
              <span
                className="text-[10px] uppercase font-bold tracking-widest"
                style={{ color: "var(--outline-variant)" }}
              >
                Skip
              </span>
            </button>
          </div>

          <div
            className="hidden lg:flex mt-8 gap-8 text-[11px] font-bold uppercase tracking-[0.15em]"
            style={{ color: "var(--outline-variant)" }}
          >
            <span className="flex items-center gap-2">
              <kbd
                className="px-2 py-1 rounded"
                style={{ background: "var(--surface-container-low)" }}
              >
                SPACE
              </kbd>{" "}
              Reveal
            </span>
            <span className="flex items-center gap-2">
              <kbd
                className="px-2 py-1 rounded"
                style={{ background: "var(--surface-container-low)" }}
              >
                ←
              </kbd>{" "}
              Wrong
            </span>
            <span className="flex items-center gap-2">
              <kbd
                className="px-2 py-1 rounded"
                style={{ background: "var(--surface-container-low)" }}
              >
                →
              </kbd>{" "}
              Correct
            </span>
          </div>
        </section>
      </div>
    );
  }

  // Results view
  if (view === "results") {
    const total = results.length;
    const correct = results.filter((r) => r.correct).length;
    const wrong = total - correct;
    return (
      <div>
        <div className="mb-10">
          <span className="text-xs font-bold tracking-[0.1em] text-[#436565] uppercase mb-2 block">
            Session Complete
          </span>
          <h1
            className="text-4xl font-extrabold tracking-tight"
            style={{ color: "var(--dark)" }}
          >
            Well Done!
          </h1>
          <p className="mt-2 text-[#596060]">Here's how you did</p>
        </div>
        <div className="grid grid-cols-12 gap-6 mb-10 max-w-2xl">
          <div
            className="col-span-4 rounded-[2rem] p-8"
            style={{
              background: "var(--white)",
              boxShadow: "0 8px 32px rgba(45,52,51,0.06)",
            }}
          >
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center mb-4"
              style={{ background: "var(--surface-container-low)" }}
            >
              <span
                className="material-symbols-outlined"
                style={{ color: "var(--primary)" }}
              >
                style
              </span>
            </div>
            <div
              className="text-5xl font-extrabold"
              style={{ color: "var(--dark)" }}
            >
              {total}
            </div>
            <div className="text-sm mt-1 font-medium text-[#596060]">
              Total Cards
            </div>
          </div>
          <div
            className="col-span-4 rounded-[2rem] p-8"
            style={{ background: "var(--tertiary-container)" }}
          >
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center mb-4"
              style={{ background: "rgba(255,255,255,0.5)" }}
            >
              <span
                className="material-symbols-outlined"
                style={{ color: "#166534" }}
              >
                check_circle
              </span>
            </div>
            <div
              className="text-5xl font-extrabold"
              style={{ color: "#166534" }}
            >
              {correct}
            </div>
            <div className="text-sm mt-1 font-medium text-[#596060]">
              Correct
            </div>
          </div>
          <div
            className="col-span-4 rounded-[2rem] p-8"
            style={{ background: "var(--surface-container-low)" }}
          >
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center mb-4"
              style={{ background: "var(--white)" }}
            >
              <span
                className="material-symbols-outlined"
                style={{ color: "#991b1b" }}
              >
                cancel
              </span>
            </div>
            <div
              className="text-5xl font-extrabold"
              style={{ color: "#991b1b" }}
            >
              {wrong}
            </div>
            <div className="text-sm mt-1 font-medium text-[#596060]">Wrong</div>
          </div>
        </div>
        <div
          className="rounded-[2rem] p-8 max-w-2xl"
          style={{ background: "var(--surface-container-low)" }}
        >
          <h3
            className="text-lg font-bold mb-4"
            style={{ color: "var(--dark)" }}
          >
            Review
          </h3>
          <div className="space-y-3">
            {results.map((r, i) => (
              <div
                key={i}
                className="rounded-xl px-4 py-3 flex items-center gap-3"
                style={{
                  background: "var(--white)",
                  ...(r.correct
                    ? { background: "rgba(239, 254, 229, 0.3)" }
                    : {}),
                }}
              >
                {r.correct ? (
                  <span
                    className="material-symbols-outlined"
                    style={{
                      color: "#22c55e",
                      fontSize: 20,
                      fontVariationSettings: "'FILL' 1",
                    }}
                  >
                    check_circle
                  </span>
                ) : (
                  <span
                    className="material-symbols-outlined"
                    style={{
                      color: "#ef4444",
                      fontSize: 20,
                      fontVariationSettings: "'FILL' 1",
                    }}
                  >
                    cancel
                  </span>
                )}
                <span
                  className="font-bold text-sm"
                  style={{ color: "var(--dark)" }}
                >
                  {r.word}
                </span>
                <span className="text-sm" style={{ color: "var(--accent1)" }}>
                  — {r.translation}
                </span>
                <button
                  onClick={() => speakText(r.word)}
                  className="p-1 rounded-full transition-colors"
                  style={{ color: "var(--outline-variant)" }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.color = "var(--primary)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.color = "var(--outline-variant)")
                  }
                >
                  <span
                    className="material-symbols-outlined"
                    style={{ fontSize: 18 }}
                  >
                    volume_up
                  </span>
                </button>
                {r.new_fluency && (
                  <span
                    className={`ml-auto fluency-${r.new_fluency} px-2 py-0.5 rounded-full text-xs font-medium`}
                  >
                    {r.new_fluency}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
        <div className="flex gap-3 mt-8">
          <button
            onClick={resetSession}
            className="btn-primary px-6 py-3 rounded-xl text-sm font-medium"
          >
            New Session
          </button>
          <button
            onClick={() => navigate(`/${currentLanguageSlug}/vocabulary`)}
            className="btn-secondary px-6 py-3 rounded-xl text-sm font-medium"
          >
            Back to Language
          </button>
        </div>
      </div>
    );
  }

  return null;
}
