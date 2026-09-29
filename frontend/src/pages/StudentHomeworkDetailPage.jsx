import { useState, useEffect, useRef, useCallback } from "react";
import { useApp } from "../context/AppContext";
import { Page, PageHeader, Card, Button, EmptyState, LoadingState } from "../components/ui/index.jsx";

// ─── Inline Flashcard Session ────────────────────────────────────────────────
function FlashcardSession({ deck, onComplete }) {
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [correct, setCorrect] = useState(0);
  const [total, setTotal] = useState(deck.length);

  function answer(isCorrect) {
    if (isCorrect) setCorrect((c) => c + 1);
    const next = index + 1;
    if (next >= deck.length) {
      const score = ((isCorrect ? correct + 1 : correct) / total) * 100;
      onComplete(Math.round(score));
    } else {
      setIndex(next);
      setFlipped(false);
    }
  }

  if (deck.length === 0) {
    return (
      <div className="text-center py-8 text-sm" style={{ color: "var(--accent1)" }}>No vocab words in this homework.</div>
    );
  }

  const card = deck[index];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-xs" style={{ color: "var(--accent1)" }}>
        <span>{index + 1} / {total}</span>
        <span>{correct} correct</span>
      </div>
      {/* Card */}
      <div
        className="rounded-2xl p-8 text-center cursor-pointer min-h-36 flex flex-col items-center justify-center"
        style={{ background: "var(--surface)", border: "2px solid rgba(172,179,178,0.2)" }}
        onClick={() => setFlipped((f) => !f)}
      >
        <p className="text-xl font-bold" style={{ color: "var(--dark)" }}>
          {flipped ? card.native_translation : card.target_word}
        </p>
        {!flipped && (
          <p className="text-xs mt-3" style={{ color: "var(--accent1)" }}>Tap to reveal</p>
        )}
        {flipped && card.example_sentence && (
          <p className="text-sm mt-3 italic" style={{ color: "var(--accent1)" }}>{card.example_sentence}</p>
        )}
      </div>
      {flipped && (
        <div className="flex gap-3">
          <button onClick={() => answer(false)} className="flex-1 py-3 rounded-xl font-semibold text-sm" style={{ background: "rgba(239,68,68,0.1)", color: "#ef4444" }}>
            <span className="material-symbols-outlined block mb-0.5" style={{ fontSize: 18 }}>close</span>
            Again
          </button>
          <button onClick={() => answer(true)} className="flex-1 py-3 rounded-xl font-semibold text-sm" style={{ background: "rgba(34,197,94,0.1)", color: "#22c55e" }}>
            <span className="material-symbols-outlined block mb-0.5" style={{ fontSize: 18 }}>check</span>
            Got it
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Inline Grammar Session ───────────────────────────────────────────────────
function GrammarSession({ questions, onComplete }) {
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [correct, setCorrect] = useState(0);
  const textareaRef = useRef(null);

  useEffect(() => { textareaRef.current?.focus(); }, [index]);

  if (questions.length === 0) {
    return <div className="text-center py-8 text-sm" style={{ color: "var(--accent1)" }}>No questions saved for this homework yet.</div>;
  }

  const q = questions[index];

  function submit() {
    if (!answer.trim()) return;
    const isCorrect = answer.trim().toLowerCase() === q.correct_answer?.trim().toLowerCase();
    if (isCorrect) setCorrect((c) => c + 1);
    setFeedback({ isCorrect, correct_answer: q.correct_answer, explanation: q.explanation });
  }

  function next() {
    setFeedback(null);
    setAnswer("");
    const nextIdx = index + 1;
    if (nextIdx >= questions.length) {
      onComplete(Math.round((correct + (feedback?.isCorrect ? 0 : 0)) / questions.length * 100));
    } else {
      setIndex(nextIdx);
    }
  }

  function handleNext() {
    if (!feedback) { submit(); } else { next(); }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-xs" style={{ color: "var(--accent1)" }}>
        <span>Q{index + 1} / {questions.length}</span>
        <span className="px-2 py-0.5 rounded-full capitalize" style={{ background: "var(--surface-container)" }}>{q.question_type}</span>
      </div>
      <div className="rounded-2xl p-4" style={{ background: "var(--surface)" }}>
        <p className="font-semibold mb-2" style={{ color: "var(--dark)" }}>{q.question_text}</p>
        {q.english_prompt && <p className="text-sm mb-2 italic" style={{ color: "var(--accent1)" }}>"{q.english_prompt}"</p>}
        {q.wrong_sentence && (
          <p className="text-sm mb-2 px-3 py-2 rounded-xl" style={{ background: "rgba(239,68,68,0.08)", color: "#ef4444" }}>
            {q.wrong_sentence}
          </p>
        )}
        <textarea
          ref={textareaRef}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleNext(); } }}
          disabled={!!feedback}
          rows={2}
          placeholder="Your answer..."
          className="w-full px-3 py-2 rounded-xl text-sm border resize-none mt-2"
          style={{ background: "var(--surface-container)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }}
        />
      </div>
      {feedback && (
        <div className="rounded-2xl p-4 space-y-1" style={{ background: feedback.isCorrect ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)" }}>
          <p className="font-semibold text-sm" style={{ color: feedback.isCorrect ? "#22c55e" : "#ef4444" }}>
            {feedback.isCorrect ? "Correct!" : "Not quite"}
          </p>
          {!feedback.isCorrect && <p className="text-sm" style={{ color: "var(--dark)" }}>Answer: <strong>{feedback.correct_answer}</strong></p>}
          {feedback.explanation && <p className="text-sm" style={{ color: "var(--accent1)" }}>{feedback.explanation}</p>}
        </div>
      )}
      <button onClick={handleNext} className="w-full py-3 rounded-xl text-sm font-semibold text-white" style={{ background: "var(--primary)" }}>
        {!feedback ? "Check Answer" : index + 1 >= questions.length ? "Finish" : "Next"}
      </button>
    </div>
  );
}

// ─── Exercise Card ────────────────────────────────────────────────────────────
function ExerciseCard({ title, icon, subtitle, done, score, children, onStart, active, buttonLabel }) {
  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface-container)" }}>
      <div className="px-5 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "rgba(67,101,101,0.1)" }}>
            <span className="material-symbols-outlined" style={{ fontSize: 20, color: "var(--primary)" }}>{icon}</span>
          </div>
          <div>
            <p className="font-bold text-sm" style={{ color: "var(--dark)" }}>{title}</p>
            <p className="text-xs" style={{ color: "var(--accent1)" }}>{subtitle}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {done && (
            <div className="flex items-center gap-1">
              <span className="material-symbols-outlined" style={{ fontSize: 16, color: "#22c55e" }}>check_circle</span>
              {score != null && <span className="text-xs font-semibold" style={{ color: "#22c55e" }}>{score}%</span>}
            </div>
          )}
          {!active && (
            <button onClick={onStart} className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-white" style={{ background: "var(--primary)" }}>
              {buttonLabel || (done ? "Redo" : "Start")}
            </button>
          )}
        </div>
      </div>
      {active && (
        <div className="px-5 pb-5 border-t" style={{ borderColor: "rgba(172,179,178,0.15)" }}>
          <div className="pt-4">{children}</div>
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function StudentHomeworkDetailPage({ homeworkId }) {
  const { apiFetch, navigate, currentLanguageSlug, setPendingConversationTopic } = useApp();
  const [hw, setHw] = useState(null);
  const [loading, setLoading] = useState(true);
  const [completions, setCompletions] = useState({});
  const [activeExercise, setActiveExercise] = useState(null); // 'flashcards' | 'grammar' | 'conversation'
  const [flashcardDeck, setFlashcardDeck] = useState([]);
  const [startingFlashcards, setStartingFlashcards] = useState(false);

  const loadHw = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await apiFetch(`/api/student/homework/${homeworkId}`);
      if (resp.ok) {
        const data = await resp.json();
        setHw(data);
        // completions comes back as { exercise_type: { score, completed_at } } dict
        setCompletions(data.completions || {});
      }
    } finally {
      setLoading(false);
    }
  }, [homeworkId, apiFetch]);

  useEffect(() => { loadHw(); }, [loadHw]);

  async function recordCompletion(type, score) {
    const resp = await apiFetch(`/api/student/homework/${homeworkId}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exercise_type: type, score }),
    });
    if (resp.ok) {
      setCompletions((prev) => ({ ...prev, [type]: { score } }));
    }
    setActiveExercise(null);
  }

  async function startFlashcards() {
    setStartingFlashcards(true);
    try {
      const resp = await apiFetch(`/api/student/homework/${homeworkId}/start-flashcards`, { method: "POST" });
      if (!resp.ok) { alert("Failed to start flashcards"); return; }
      const data = await resp.json();
      // Shuffle deck
      const deck = [...(data.deck || [])];
      for (let i = deck.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [deck[i], deck[j]] = [deck[j], deck[i]];
      }
      setFlashcardDeck(deck);
      setActiveExercise("flashcards");
    } finally {
      setStartingFlashcards(false);
    }
  }

  function launchConversation(topic) {
    // Navigate to the student's own Conversation Practice page with the topic pre-loaded.
    // The PracticePage reads pendingConversationTopic from context on mount.
    setPendingConversationTopic(topic);
    const slug = currentLanguageSlug;
    if (slug) {
      navigate(`/${slug}/practice`);
    } else {
      // Fallback: navigate to practice without a language prefix; user selects language there
      navigate("/practice");
    }
  }

  // Build flat questions list from all grammar concepts
  const allGrammarQuestions = (hw?.grammar || []).flatMap((g) => g.questions || []);

  if (loading) {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (!hw) {
    return (
      <Page>
        <Card>
          <EmptyState
            icon="search_off"
            title="Homework not found"
            description="This assignment doesn't exist or you don't have access to it."
            action={<Button variant="secondary" icon="arrow_back" onClick={() => navigate("/homework")}>Back to Homework</Button>}
          />
        </Card>
      </Page>
    );
  }

  const isOverdue = hw.due_date && new Date(hw.due_date) < new Date();

  return (
    <Page>
      <PageHeader
        onBack={() => navigate("/homework")}
        eyebrow={hw.class_name}
        title={hw.name}
        subtitle={
          hw.due_date ? (
            <span className="inline-flex items-center gap-1 text-sm" style={{ color: isOverdue ? "#ef4444" : undefined }}>
              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>calendar_today</span>
              {isOverdue ? "Overdue: " : "Due: "}{new Date(hw.due_date).toLocaleDateString()}
            </span>
          ) : undefined
        }
        className="!mb-6"
      />

      {hw.description && (
        <Card variant="tonal" padding="sm" className="mb-5 text-sm text-[var(--dark)]">
          {hw.description}
        </Card>
      )}

      {/* Overall progress */}
      {Object.keys(completions).length > 0 && (
        <div className="flex items-center gap-4 mb-6 px-1">
          <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--accent1)" }}>Progress</span>
          {["flashcards", "grammar", "conversation"].map((type) => (
            completions[type] ? (
              <div key={type} className="flex items-center gap-1 text-xs" style={{ color: "#22c55e" }}>
                <span className="material-symbols-outlined" style={{ fontSize: 13 }}>check_circle</span>
                <span className="capitalize">{type}</span>
              </div>
            ) : (
              <div key={type} className="flex items-center gap-1 text-xs" style={{ color: "var(--accent1)", opacity: 0.5 }}>
                <span className="material-symbols-outlined" style={{ fontSize: 13 }}>radio_button_unchecked</span>
                <span className="capitalize">{type}</span>
              </div>
            )
          ))}
        </div>
      )}

      {/* Exercises */}
      <div className="space-y-4">
        {/* Flashcards */}
        <ExerciseCard
          title="Flashcards"
          icon="style"
          subtitle={`${hw.vocab?.length || 0} vocabulary words`}
          done={!!completions.flashcards}
          score={completions.flashcards?.score}
          active={activeExercise === "flashcards"}
          onStart={startFlashcards}
          buttonLabel={startingFlashcards ? "Loading..." : undefined}
        >
          <FlashcardSession
            deck={flashcardDeck}
            onComplete={(score) => recordCompletion("flashcards", score)}
          />
        </ExerciseCard>

        {/* Grammar */}
        <ExerciseCard
          title="Grammar Practice"
          icon="spellcheck"
          subtitle={`${hw.grammar?.length || 0} concepts · ${allGrammarQuestions.length} questions`}
          done={!!completions.grammar}
          score={completions.grammar?.score}
          active={activeExercise === "grammar"}
          onStart={() => setActiveExercise("grammar")}
        >
          <GrammarSession
            questions={allGrammarQuestions}
            onComplete={(score) => recordCompletion("grammar", score)}
          />
        </ExerciseCard>

        {/* Conversation */}
        <ExerciseCard
          title="Conversation Practice"
          icon="chat"
          subtitle={`${hw.topics?.length || 0} topic${hw.topics?.length !== 1 ? "s" : ""}`}
          done={!!completions.conversation}
          score={completions.conversation?.score != null ? completions.conversation.score : null}
          active={activeExercise === "conversation"}
          onStart={() => setActiveExercise("conversation")}
        >
          <div className="space-y-3">
            {hw.topics?.length > 0 ? (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--accent1)" }}>
                  Pick a topic to practise
                </p>
                {hw.topics.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => launchConversation(t.topic_text)}
                    className="w-full flex items-center justify-between px-4 py-3 rounded-xl text-sm mb-1.5 text-left"
                    style={{ background: "var(--surface)", color: "var(--dark)" }}
                  >
                    <span>{t.topic_text}</span>
                    <span className="material-symbols-outlined ml-2 shrink-0" style={{ fontSize: 16, color: "var(--primary)" }}>open_in_new</span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-sm text-center py-4" style={{ color: "var(--accent1)" }}>No conversation topics set for this homework.</p>
            )}
            <div className="pt-1">
              <Button full onClick={() => recordCompletion("conversation", null)}>
                Mark as Complete
              </Button>
            </div>
          </div>
        </ExerciseCard>
      </div>
    </Page>
  );
}
