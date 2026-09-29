import { useState, useEffect, useRef } from "react";
import CreditIcon from "../components/CreditIcon";
import { playAudio } from "../utils.jsx";
import { useApp } from "../context/AppContext.jsx";
import { Page, PageHeader, Card, Button, Eyebrow, SectionTitle } from "../components/ui/index.jsx";

export default function PracticePage() {
  const {
    currentLanguageId,
    currentLanguageName,
    currentLanguageSlug,
    apiFetch,
    navigate,
    showLoading,
    hideLoading,
    fetchTopics,
    fetchStats,
    pendingConversationTopic,
    setPendingConversationTopic,
  } = useApp();
  const [view, setView] = useState("setup"); // 'setup' | 'active' | 'analysis'

  // Setup state
  const [mode, setMode] = useState("lesson"); // 'lesson' | 'scenario'
  const [topicGroups, setTopicGroups] = useState([]);
  const [selectedTopicId, setSelectedTopicId] = useState(null);
  const [customScenario, setCustomScenario] = useState("");
  const [vocabCount, setVocabCount] = useState(null);

  // Conversation state
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState("");
  const [recording, setRecording] = useState(false);
  const [processingAudio, setProcessingAudio] = useState(false);
  const [isTyping, setIsTyping] = useState(false);

  // Analysis state
  const [analysis, setAnalysis] = useState(null);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const messagesEndRef = useRef(null);
  const textInputRef = useRef(null);

  useEffect(() => {
    if (currentLanguageId) {
      loadTopics();
      loadStats();
    }
  }, [currentLanguageId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-start scenario when navigated here from homework
  useEffect(() => {
    if (pendingConversationTopic && currentLanguageId && view === "setup") {
      setMode("scenario");
      setCustomScenario(pendingConversationTopic);
      setPendingConversationTopic(null);
    }
  }, [pendingConversationTopic, currentLanguageId]); // eslint-disable-line

  async function loadTopics() {
    const data = await fetchTopics(currentLanguageId);
    setTopicGroups(data.clusters || []);
  }

  async function loadStats() {
    const data = await fetchStats(currentLanguageId);
    setVocabCount(data?.total_vocabulary ?? 0);
  }

  async function startSession() {
    showLoading("Starting your session...");
    try {
      let resp;
      if (mode === "lesson") {
        const params = new URLSearchParams();
        if (selectedTopicId) params.append("topic_id", selectedTopicId);
        resp = await apiFetch(
          `/api/start-lesson/${currentLanguageId}?${params}`,
          { method: "POST" },
        );
      } else {
        const body = new FormData();
        if (customScenario.trim())
          body.append("scenario", customScenario.trim());
        resp = await apiFetch(`/api/start-scenario/${currentLanguageId}`, {
          method: "POST",
          body,
        });
      }
      if (!resp.ok) {
        let detail = "Failed to start session";
        try {
          const err = await resp.json();
          if (err.detail) detail = err.detail;
        } catch {}
        alert(detail);
        hideLoading();
        return;
      }
      const data = await resp.json();
      setSessionId(data.session_id);
      const firstMsg = {
        role: "assistant",
        content:
          data.opening_message ||
          data.message ||
          data.greeting ||
          "Hello! Let's begin.",
        translation: data.opening_translation || data.translation,
        romanization: data.opening_romanization || null,
        audio: data.audio,
      };
      setMessages([firstMsg]);
      setView("active");
    } catch (e) {
      console.error(e);
      alert("Error starting session");
    } finally {
      hideLoading();
    }
  }

  async function sendText() {
    const text = inputText.trim();
    if (!text || !sessionId) return;
    setInputText("");
    setMessages((msgs) => [...msgs, { role: "user", content: text }]);
    setIsTyping(true);
    await sendResponse({ text });
    setIsTyping(false);
  }

  async function sendResponse({ text, audioBlob }) {
    const formData = new FormData();
    if (text) formData.append("text", text);
    if (audioBlob) formData.append("audio", audioBlob, "recording.webm");
    try {
      const resp = await apiFetch(`/api/conversation/${sessionId}/respond`, {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) return;
      const data = await resp.json();
      if (data.user_message && audioBlob) {
        setMessages((msgs) => [
          ...msgs.slice(0, -0),
          { role: "user", content: data.user_message },
        ]);
      }
      setMessages((msgs) => [
        ...msgs,
        {
          role: "assistant",
          content: data.response,
          translation: data.translation,
          romanization: data.romanization || null,
          audio: data.audio,
        },
      ]);
    } catch (e) {
      console.error(e);
    }
  }

  async function startRecording() {
    if (!navigator.mediaDevices) {
      alert("Microphone not supported");
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunksRef.current = [];
    const mr = new MediaRecorder(stream);
    mr.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunksRef.current.push(e.data);
    };
    mr.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
      setProcessingAudio(true);
      setIsTyping(true);
      setMessages((msgs) => [
        ...msgs,
        { role: "user", content: "🎤 Voice message...", pending: true },
      ]);
      await sendResponse({ audioBlob: blob });
      setProcessingAudio(false);
      setIsTyping(false);
    };
    mr.start();
    mediaRecorderRef.current = mr;
    setRecording(true);
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }

  async function endConversation() {
    if (!sessionId) return;
    showLoading("Analysing your session...");
    try {
      const resp = await apiFetch(`/api/conversation/${sessionId}/end`, {
        method: "POST",
      });
      if (!resp.ok) {
        hideLoading();
        return;
      }
      const data = await resp.json();
      setAnalysis(data.analysis);
      setView("analysis");
    } catch (e) {
      console.error(e);
      alert("Error ending session");
    } finally {
      hideLoading();
    }
  }

  function resetSession() {
    setView("setup");
    setSessionId(null);
    setMessages([]);
    setAnalysis(null);
    setInputText("");
  }

  // ---- Setup View ----
  if (view === "setup") {
    const modes = [
      { key: "lesson", icon: "auto_stories", title: "Lesson", desc: "AI will choose the topic" },
      { key: "scenario", icon: "theater_comedy", title: "Scenario", desc: "Choose your own topic" },
    ];
    return (
      <Page>
        <PageHeader
          title="Practice Conversation"
          subtitle="Choose your practice mode and start speaking"
        />

        <div className="space-y-6">
            {/* Mode selector */}
            <Card padding="md">
              <SectionTitle>Practice Mode</SectionTitle>
              <div className="grid grid-cols-2 gap-4">
                {modes.map((m) => (
                  <Card
                    key={m.key}
                    variant="tonal"
                    padding="md"
                    interactive
                    selected={mode === m.key}
                    className="!rounded-2xl"
                    onClick={() => setMode(m.key)}
                  >
                    <span className="material-symbols-outlined mb-3 block text-[var(--primary)]" style={{ fontSize: 28 }}>
                      {m.icon}
                    </span>
                    <h4 className="font-semibold text-[var(--dark)]">{m.title}</h4>
                    <p className="text-xs mt-1 text-[var(--accent1)]">{m.desc}</p>
                  </Card>
                ))}
              </div>
            </Card>

            {mode === "lesson" && topicGroups.length > 0 && (
              <Card padding="md">
                <SectionTitle>
                  Choose a Topic <span className="font-normal text-[var(--accent1)]">(optional)</span>
                </SectionTitle>
                <div className="space-y-4">
                  {topicGroups.map((group, gi) => (
                    <div key={gi}>
                      <Eyebrow tone="primary" className="mb-2">{group.theme}</Eyebrow>
                      <div className="flex flex-wrap gap-2">
                        {group.topics.map((t, ti) => (
                          <button
                            key={t.id || ti}
                            onClick={() => setSelectedTopicId(selectedTopicId === t.id ? null : t.id)}
                            className={`px-4 py-2 rounded-full text-xs font-medium transition-all ${selectedTopicId === t.id ? "btn-primary" : "btn-secondary"}`}
                          >
                            {t.name}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {mode === "scenario" && (
              <Card padding="md">
                <SectionTitle>
                  Describe Your Scenario <span className="font-normal text-[var(--accent1)]">(optional)</span>
                </SectionTitle>
                <textarea
                  className="input-field w-full p-4 rounded-xl text-sm resize-none"
                  rows={4}
                  placeholder="e.g. I'm at a restaurant and I want to order food and ask about the menu..."
                  value={customScenario}
                  onChange={(e) => setCustomScenario(e.target.value)}
                />
              </Card>
            )}

            {vocabCount === 0 && (
              <div className="rounded-2xl p-6 bg-red-50 border border-red-200">
                <div className="flex items-start gap-3">
                  <span className="material-symbols-outlined shrink-0 text-red-800">info</span>
                  <div>
                    <h4 className="font-semibold text-red-800">No vocabulary yet</h4>
                    <p className="text-sm mt-1 text-red-800">
                      Conversations are built from your personal vocabulary. Add
                      some {currentLanguageName} words first to start practicing.
                    </p>
                    <div className="flex flex-wrap gap-2 mt-4">
                      <Button size="sm" onClick={() => navigate(`/${currentLanguageSlug}/notes`)}>
                        Upload Notes
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => navigate(`/${currentLanguageSlug}/placement`)}>
                        Take Placement Test
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <Button size="xl" full icon="mic" onClick={startSession} disabled={vocabCount === 0}>
              Start Session
              <CreditIcon />
            </Button>
        </div>
      </Page>
    );
  }

  // ---- Active Conversation View ----
  if (view === "active") {
    return (
      <Page className="flex flex-col" style={{ height: "calc(100vh - 120px)" }}>
        <PageHeader
          eyebrow="Active Session"
          title="Practice Session"
          subtitle={`${currentLanguageName} — ${mode === "lesson" ? "Lesson" : "Scenario"}`}
          className="!mb-6 shrink-0"
          actions={
            <Button variant="danger" icon="stop_circle" onClick={endConversation}>
              End &amp; Analyse
            </Button>
          }
        />

        <div className="flex-1 overflow-y-auto space-y-4 px-2 pb-4">
          {messages.map((msg, i) => (
            <MessageBubble
              key={i}
              msg={msg}
              isPersian={currentLanguageName === "Persian"}
            />
          ))}
          {isTyping && <TypingIndicator />}
          <div ref={messagesEndRef} />
        </div>

        <div className="shrink-0 pt-4 pb-2">
          <div className="flex items-center gap-3">
            <button
              onClick={recording ? stopRecording : startRecording}
              className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${recording ? "bg-red-500 text-white" : "bg-[var(--surface-container-low)] text-[var(--primary)]"}`}
            >
              <span className="material-symbols-outlined">
                {recording ? "stop" : "mic"}
              </span>
            </button>
            <input
              ref={textInputRef}
              className="input-field flex-1 px-5 py-3 rounded-xl text-sm"
              placeholder="Or type your message..."
              value={inputText}
              disabled={isTyping}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) =>
                e.key === "Enter" && !e.shiftKey && !isTyping && sendText()
              }
            />
            <button
              onClick={sendText}
              disabled={!inputText.trim() || isTyping}
              className="w-12 h-12 rounded-full flex items-center justify-center disabled:opacity-40 bg-[var(--primary)] text-[var(--on-primary)]"
            >
              <span className="material-symbols-outlined">send</span>
            </button>
          </div>
          {recording && (
            <p className="text-xs text-center mt-2 font-medium animate-pulse text-red-500">
              Recording... tap stop when done
            </p>
          )}
        </div>
      </Page>
    );
  }

  // ---- Analysis View ----
  if (view === "analysis" && analysis) {
    return (
      <Page>
        <PageHeader
          eyebrow="Session Complete"
          title="Session Analysis"
          subtitle="Here's how you did"
          actions={<Button onClick={resetSession}>New Session</Button>}
        />

        {analysis.overall_feedback && (
          <Card className="mb-6">
            <SectionTitle>Overall Feedback</SectionTitle>
            <p className="text-[var(--accent1)]">{analysis.overall_feedback}</p>
          </Card>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-6">
          {analysis.correct_words && analysis.correct_words.length > 0 && (
            <Card variant="accent" padding="md">
              <h3 className="text-lg font-bold mb-3 text-[#166534]">Words Used Correctly</h3>
              <ul className="space-y-2">
                {analysis.correct_words.map((w, i) => (
                  <li key={i} className="flex gap-2 text-sm">
                    <span
                      className="material-symbols-outlined text-base"
                      style={{ color: "#22c55e", fontVariationSettings: "'FILL' 1" }}
                    >
                      check_circle
                    </span>
                    <span>
                      <strong>{w.word}</strong>
                      {w.translation ? ` — ${w.translation}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {analysis.incorrect_words && analysis.incorrect_words.length > 0 && (
            <Card variant="tonal" padding="md">
              <SectionTitle>Words to Improve</SectionTitle>
              <ul className="space-y-2">
                {analysis.incorrect_words.map((w, i) => (
                  <li key={i} className="flex gap-2 text-sm">
                    <span className="material-symbols-outlined text-base text-[var(--primary)]">arrow_forward</span>
                    <span>
                      <strong>{w.word}</strong>
                      {w.correction ? ` → ${w.correction}` : ""}
                      {w.explanation ? (
                        <em className="block text-xs text-[var(--accent1)]">{w.explanation}</em>
                      ) : null}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        {analysis.correct_grammar && analysis.correct_grammar.length > 0 && (
          <Card padding="md" className="mb-6">
            <SectionTitle>Grammar Used Well</SectionTitle>
            <ul className="space-y-2">
              {analysis.correct_grammar.map((g, i) => (
                <li key={i} className="text-sm">
                  <strong>{g.pattern}</strong>
                  {g.example ? `: "${g.example}"` : ""}
                </li>
              ))}
            </ul>
          </Card>
        )}

        {analysis.incorrect_grammar && analysis.incorrect_grammar.length > 0 && (
          <Card padding="md" className="mb-6">
            <SectionTitle>Grammar to Review</SectionTitle>
            <ul className="space-y-2">
              {analysis.incorrect_grammar.map((g, i) => (
                <li key={i} className="text-sm">
                  <strong>{g.pattern}</strong>: "{g.student_said}" → "{g.correction}"
                  {g.explanation ? (
                    <em className="block text-xs text-[var(--accent1)]">{g.explanation}</em>
                  ) : null}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </Page>
    );
  }

  return null;
}

function MessageBubble({ msg, isPersian }) {
  const [showTranslation, setShowTranslation] = useState(false);
  const [showRomanization, setShowRomanization] = useState(false);
  const isUser = msg.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center mr-3 shrink-0 mt-1"
          style={{
            background: "var(--primary)",
            color: "var(--on-primary)",
            fontSize: 14,
          }}
        >
          AI
        </div>
      )}
      <div className={`max-w-md ${isUser ? "ml-12" : "mr-12"}`}>
        <div
          className={`px-5 py-4 rounded-2xl text-sm ${isUser ? "text-white" : ""}`}
          style={
            isUser
              ? {
                  background: "var(--primary)",
                  borderRadius: "1.25rem 1.25rem 0.5rem 1.25rem",
                }
              : {
                  background: "var(--white)",
                  boxShadow: "0 4px 16px rgba(45,52,51,0.06)",
                  borderRadius: "0.5rem 1.25rem 1.25rem 1.25rem",
                }
          }
        >
          <p style={{ color: isUser ? "var(--on-primary)" : "var(--dark)" }}>
            {msg.content}
          </p>
          {!isUser && showRomanization && msg.romanization && (
            <p
              className="mt-2 text-xs font-medium"
              style={{ color: "var(--primary)", direction: "ltr" }}
            >
              {msg.romanization}
            </p>
          )}
          {!isUser && showTranslation && msg.translation && (
            <p
              className="mt-2 text-xs italic"
              style={{ color: "var(--accent1)" }}
            >
              {msg.translation}
            </p>
          )}
        </div>
        {!isUser &&
          (msg.translation || msg.audio || (isPersian && msg.romanization)) && (
            <div className="flex gap-2 mt-1.5 ml-2 flex-wrap">
              {isPersian && msg.romanization && (
                <button
                  onClick={() => setShowRomanization((r) => !r)}
                  className="text-xs px-3 py-1 rounded-full transition-colors"
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
              {msg.translation && (
                <button
                  onClick={() => setShowTranslation((t) => !t)}
                  className="text-xs px-3 py-1 rounded-full transition-colors"
                  style={{
                    background: "var(--surface-container-low)",
                    color: "var(--accent1)",
                  }}
                >
                  {showTranslation ? "Hide" : "Translate"}
                </button>
              )}
              {msg.audio && (
                <button
                  onClick={() => playAudio(msg.audio)}
                  className="text-xs px-3 py-1 rounded-full transition-colors flex items-center gap-1"
                  style={{
                    background: "var(--surface-container-low)",
                    color: "var(--accent1)",
                  }}
                >
                  <span
                    className="material-symbols-outlined"
                    style={{ fontSize: 14 }}
                  >
                    volume_up
                  </span>
                </button>
              )}
            </div>
          )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center mr-3 shrink-0"
        style={{
          background: "var(--primary)",
          color: "var(--on-primary)",
          fontSize: 14,
        }}
      >
        AI
      </div>
      <div
        className="px-5 py-3 rounded-2xl typing-indicator"
        style={{
          background: "var(--white)",
          boxShadow: "0 4px 16px rgba(45,52,51,0.06)",
        }}
      >
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}
