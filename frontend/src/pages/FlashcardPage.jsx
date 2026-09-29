import { useState, useEffect, useRef, useCallback } from "react";
import { useApp } from "../context/AppContext";
import { speakText } from "../utils.jsx";
import {
  Page,
  PageHeader,
  Card,
  Button,
  IconTile,
  Eyebrow,
  SectionTitle,
  FluencyBadge,
  ResultSummary,
  ResultRow,
} from "../components/ui/index.jsx";

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
      <Page>
        <PageHeader
          title={`${currentLanguageName} Flashcards`}
          subtitle="Review your vocabulary with flashcards"
        />
        <div className="space-y-6">
          <Card padding="md">
            <SectionTitle>Show me the word in</SectionTitle>
            <div className="space-y-6">
            <div>
              <div className="grid grid-cols-2 gap-3">
                <Button size="lg" variant={direction === "target" ? "primary" : "secondary"} onClick={() => setDirection("target")}>
                  {currentLanguageName}
                </Button>
                <Button size="lg" variant={direction === "native" ? "primary" : "secondary"} onClick={() => setDirection("native")}>
                  {nativeLanguage}
                </Button>
              </div>
            </div>
            <div>
              <SectionTitle>Filter by fluency</SectionTitle>
              <div className="grid grid-cols-4 gap-2">
                {["all", "low", "medium", "high"].map((level) => (
                  <Button
                    key={level}
                    size="lg"
                    variant={fluencyFilter === level ? "primary" : "secondary"}
                    className="capitalize"
                    onClick={() => setFluencyFilter(level)}
                  >
                    {level}
                  </Button>
                ))}
              </div>
            </div>
            <div className="text-sm text-center text-[var(--accent1)]">
              {wordCount} words available
            </div>
            </div>
          </Card>
          <Button size="xl" full icon="style" onClick={beginFlashcards} disabled={wordCount === 0}>
            Start Flashcards
          </Button>
        </div>
      </Page>
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
    const badge = <FluencyBadge level={card.fluency_level} />;
    const segments = Math.min(total, 10);
    const filled = Math.ceil((num / total) * segments);
    const sessionStats = [
      { icon: "check_circle", label: "Correct", value: correctCount },
      { icon: "close", label: "Wrong", value: wrongCount, iconColor: "#a83836" },
      { icon: "bolt", label: "Streak", value: streak, primary: true },
    ];

    return (
      <Page>
        <PageHeader
          eyebrow="Active Session"
          title="Flashcards"
          subtitle={`Card ${num} of ${total}`}
          actions={
            <div className="flex flex-col items-end gap-3">
              <div className="flex gap-1 w-48">
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
              <Button variant="secondary" size="sm" onClick={endSession}>
                End Session
              </Button>
            </div>
          }
        />

        <section className="flex flex-col items-center w-full">
          {/* Mobile stats strip */}
          <div className="lg:hidden w-full grid grid-cols-3 gap-3 mb-4">
            {sessionStats.map((st) => <SessionStat key={st.label} compact {...st} />)}
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
              {sessionStats.map((st) => <SessionStat key={st.label} {...st} />)}
            </div>
          </div>

          {/* Controls */}
          <Card variant="tonal" padding="none" className="mt-8 !rounded-full py-4 px-8 flex items-center gap-10">
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
          </Card>

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
      </Page>
    );
  }

  // Results view
  if (view === "results") {
    const total = results.length;
    const correct = results.filter((r) => r.correct).length;
    return (
      <Page>
        <PageHeader
          eyebrow="Session Complete"
          title="Well Done!"
          subtitle="Here's how you did"
          actions={
            <>
              <Button onClick={resetSession}>New Session</Button>
              <Button variant="secondary" onClick={() => navigate(`/${currentLanguageSlug}/vocabulary`)}>
                Back to Language
              </Button>
            </>
          }
        />
        <ResultSummary total={total} correct={correct} totalLabel="Total Cards" />
        <Card variant="tonal">
          <SectionTitle>Review</SectionTitle>
          <div className="space-y-3">
            {results.map((r, i) => (
              <ResultRow key={i} correct={r.correct}>
                <span className="font-bold text-sm text-[var(--dark)]">{r.word}</span>
                <span className="text-sm text-[var(--accent1)]">— {r.translation}</span>
                <button
                  onClick={() => speakText(r.word)}
                  className="p-1 rounded-full transition-colors text-[var(--outline-variant)] hover:text-[var(--primary)]"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
                    volume_up
                  </span>
                </button>
                {r.new_fluency && <FluencyBadge level={r.new_fluency} className="ml-auto" />}
              </ResultRow>
            ))}
          </div>
        </Card>
      </Page>
    );
  }

  return null;
}

function SessionStat({ icon, label, value, iconColor, primary = false, compact = false }) {
  return (
    <Card
      variant={primary ? "primary" : "tonal"}
      padding={compact ? "sm" : "lg"}
      className={compact ? "" : "flex-1 flex flex-col justify-center"}
    >
      <div className={`flex items-center ${compact ? "gap-3" : "gap-4"}`}>
        <IconTile
          icon={icon}
          size={compact ? "sm" : "md"}
          tone={primary ? "inverse" : "tonal"}
          className={primary ? "" : "!bg-white"}
          style={iconColor ? { color: iconColor } : undefined}
        />
        <div>
          <Eyebrow className={primary ? "!text-[var(--on-primary)] opacity-80" : ""}>{label}</Eyebrow>
          <p className={`${compact ? "text-xl" : "text-3xl"} font-extrabold ${primary ? "" : "text-[var(--dark)]"}`}>
            {value}
          </p>
        </div>
      </div>
    </Card>
  );
}
