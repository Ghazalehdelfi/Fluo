import { useState, useEffect, useRef } from "react";
import CreditIcon from "../components/CreditIcon";
import { playAudio } from "../utils.jsx";
import { useApp } from "../context/AppContext.jsx";

export default function PracticePage() {
  const {
    currentLanguageId,
    currentLanguageName,
    apiFetch,
    showLoading,
    hideLoading,
    fetchTopics,
    pendingConversationTopic,
    setPendingConversationTopic,
  } = useApp();
  const [view, setView] = useState("setup"); // 'setup' | 'active' | 'analysis'

  // Setup state
  const [mode, setMode] = useState("lesson"); // 'lesson' | 'scenario'
  const [topicGroups, setTopicGroups] = useState([]);
  const [selectedTopicId, setSelectedTopicId] = useState(null);
  const [customScenario, setCustomScenario] = useState("");

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
    if (currentLanguageId) loadTopics();
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
        alert("Failed to start session");
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
      setAnalysis(data);
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
    return (
      <div>
        <header className="mb-10">
          <h2
            className="text-4xl font-bold tracking-tight"
            style={{ color: "var(--dark)" }}
          >
            Practice Conversation
          </h2>
          <p className="text-[#596060] mt-2">
            Choose your practice mode and start speaking
          </p>
        </header>

        <div className="flex flex-col-reverse lg:grid lg:grid-cols-12 gap-8">
          <div className="lg:col-span-8 space-y-8">
            {/* Mode selector */}
            <div
              className="bg-white rounded-2xl p-6"
              style={{ boxShadow: "0 4px 16px rgba(45,52,51,0.06)" }}
            >
              <h3
                className="font-semibold mb-4"
                style={{ color: "var(--dark)" }}
              >
                Practice Mode
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div
                  onClick={() => setMode("lesson")}
                  className={`p-6 rounded-xl cursor-pointer transition-all ${mode === "lesson" ? "outline outline-2 outline-[#436565]" : ""}`}
                  style={{
                    background:
                      mode === "lesson"
                        ? "var(--surface-container-low)"
                        : "var(--surface-container-low)",
                  }}
                >
                  <span
                    className="material-symbols-outlined mb-3 block"
                    style={{ color: "var(--primary)", fontSize: 28 }}
                  >
                    auto_stories
                  </span>
                  <h4
                    className="font-semibold"
                    style={{ color: "var(--dark)" }}
                  >
                    Lesson
                  </h4>
                  <p className="text-xs mt-1 text-[#596060]">
                    AI will choose the topic
                  </p>
                </div>
                <div
                  onClick={() => setMode("scenario")}
                  className={`p-6 rounded-xl cursor-pointer transition-all ${mode === "scenario" ? "outline outline-2 outline-[#436565]" : ""}`}
                  style={{ background: "var(--surface-container-low)" }}
                >
                  <span
                    className="material-symbols-outlined mb-3 block"
                    style={{ color: "var(--primary)", fontSize: 28 }}
                  >
                    theater_comedy
                  </span>
                  <h4
                    className="font-semibold"
                    style={{ color: "var(--dark)" }}
                  >
                    Scenario
                  </h4>
                  <p className="text-xs mt-1 text-[#596060]">
                    Choose your own topic
                  </p>
                </div>
              </div>
            </div>

            {mode === "lesson" && (
              <>
                {/* Topic picker */}
                {topicGroups.length > 0 && (
                  <div
                    className="bg-white rounded-2xl p-6"
                    style={{ boxShadow: "0 4px 16px rgba(45,52,51,0.06)" }}
                  >
                    <h3
                      className="font-semibold mb-4"
                      style={{ color: "var(--dark)" }}
                    >
                      Choose a Topic{" "}
                      <span className="font-normal text-[#596060]">
                        (optional)
                      </span>
                    </h3>
                    <div className="space-y-4">
                      {topicGroups.map((group, gi) => (
                        <div key={gi}>
                          <p
                            className="text-xs font-bold uppercase tracking-widest mb-2"
                            style={{ color: "var(--primary)" }}
                          >
                            {group.theme}
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {group.topics.map((t, ti) => (
                              <button
                                key={t.id || ti}
                                onClick={() =>
                                  setSelectedTopicId(
                                    selectedTopicId === t.id ? null : t.id,
                                  )
                                }
                                className={`px-4 py-2 rounded-full text-xs font-medium transition-all ${selectedTopicId === t.id ? "btn-primary" : "btn-secondary"}`}
                              >
                                {t.name}
                              </button>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {mode === "scenario" && (
              <div
                className="bg-white rounded-2xl p-6"
                style={{ boxShadow: "0 4px 16px rgba(45,52,51,0.06)" }}
              >
                <h3
                  className="font-semibold mb-4"
                  style={{ color: "var(--dark)" }}
                >
                  Describe Your Scenario{" "}
                  <span className="font-normal text-[#596060]">(optional)</span>
                </h3>
                <textarea
                  className="input-field w-full p-4 rounded-xl text-sm resize-none"
                  rows={4}
                  placeholder="e.g. I'm at a restaurant and I want to order food and ask about the menu..."
                  value={customScenario}
                  onChange={(e) => setCustomScenario(e.target.value)}
                />
              </div>
            )}

            <button
              onClick={startSession}
              className="btn-primary w-full py-4 rounded-xl font-semibold text-lg flex items-center justify-center gap-3"
            >
              <span className="material-symbols-outlined">mic</span>
              Start Session
              <CreditIcon />
            </button>
          </div>

          <div className="lg:col-span-4">
            <div className="rounded-2xl p-6 bg-[#f1f4f3]">
              <h3
                className="font-semibold mb-4"
                style={{ color: "var(--dark)" }}
              >
                Tips
              </h3>
              <ul className="space-y-3 text-sm text-[#596060]">
                <li className="flex gap-2">
                  <span
                    className="material-symbols-outlined text-base"
                    style={{ color: "var(--primary)" }}
                  >
                    check
                  </span>
                  Speak clearly at a natural pace
                </li>
                <li className="flex gap-2">
                  <span
                    className="material-symbols-outlined text-base"
                    style={{ color: "var(--primary)" }}
                  >
                    check
                  </span>
                  Try not to switch to English
                </li>
                <li className="flex gap-2">
                  <span
                    className="material-symbols-outlined text-base"
                    style={{ color: "var(--primary)" }}
                  >
                    check
                  </span>
                  You can also type if you prefer
                </li>
                <li className="flex gap-2">
                  <span
                    className="material-symbols-outlined text-base"
                    style={{ color: "var(--primary)" }}
                  >
                    check
                  </span>
                  End the session anytime to get feedback
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---- Active Conversation View ----
  if (view === "active") {
    return (
      <div className="flex flex-col" style={{ height: "calc(100vh - 120px)" }}>
        <header className="flex justify-between items-center mb-6 shrink-0">
          <div>
            <h2 className="text-2xl font-bold" style={{ color: "var(--dark)" }}>
              Practice Session
            </h2>
            <p className="text-sm text-[#596060]">
              {currentLanguageName} —{" "}
              {mode === "lesson" ? "Lesson" : "Scenario"}
            </p>
          </div>
          <button
            onClick={endConversation}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all"
            style={{
              background: "#fef2f2",
              color: "#ef4444",
              border: "1px solid #fca5a5",
            }}
          >
            <span className="material-symbols-outlined text-base">
              stop_circle
            </span>
            End &amp; Analyse
          </button>
        </header>

        <div className="flex-1 overflow-y-auto space-y-4 px-2 pb-4">
          {messages.map((msg, i) => (
            <MessageBubble key={i} msg={msg} />
          ))}
          {isTyping && <TypingIndicator />}
          <div ref={messagesEndRef} />
        </div>

        <div className="shrink-0 pt-4 pb-2">
          <div className="flex items-center gap-3">
            <button
              onClick={recording ? stopRecording : startRecording}
              className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${recording ? "bg-red-500 text-white" : ""}`}
              style={
                !recording
                  ? {
                      background: "var(--surface-container-low)",
                      color: "var(--primary)",
                    }
                  : {}
              }
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
              className="w-12 h-12 rounded-full flex items-center justify-center disabled:opacity-40"
              style={{
                background: "var(--primary)",
                color: "var(--on-primary)",
              }}
            >
              <span className="material-symbols-outlined">send</span>
            </button>
          </div>
          {recording && (
            <p
              className="text-xs text-center mt-2 font-medium animate-pulse"
              style={{ color: "#ef4444" }}
            >
              Recording... tap stop when done
            </p>
          )}
        </div>
      </div>
    );
  }

  // ---- Analysis View ----
  if (view === "analysis" && analysis) {
    return (
      <div>
        <header className="mb-10">
          <h2
            className="text-4xl font-bold tracking-tight"
            style={{ color: "var(--dark)" }}
          >
            Session Analysis
          </h2>
          <p className="text-[#596060] mt-2">Here's how you did</p>
        </header>

        {analysis.overall_assessment && (
          <div
            className="rounded-2xl p-8 mb-8"
            style={{
              background: "var(--white)",
              boxShadow: "0 8px 32px rgba(45,52,51,0.06)",
            }}
          >
            <h3
              className="font-bold text-lg mb-3"
              style={{ color: "var(--dark)" }}
            >
              Overall Assessment
            </h3>
            <p className="text-[#596060]">{analysis.overall_assessment}</p>
          </div>
        )}

        <div className="grid grid-cols-2 gap-6 mb-8">
          {analysis.strengths && analysis.strengths.length > 0 && (
            <div
              className="rounded-2xl p-6"
              style={{ background: "var(--tertiary-container)" }}
            >
              <h3 className="font-bold mb-3" style={{ color: "#166534" }}>
                Strengths
              </h3>
              <ul className="space-y-2">
                {analysis.strengths.map((s, i) => (
                  <li key={i} className="flex gap-2 text-sm">
                    <span
                      className="material-symbols-outlined text-base"
                      style={{
                        color: "#22c55e",
                        fontVariationSettings: "'FILL' 1",
                      }}
                    >
                      check_circle
                    </span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {analysis.areas_for_improvement &&
            analysis.areas_for_improvement.length > 0 && (
              <div
                className="rounded-2xl p-6"
                style={{ background: "var(--surface-container-low)" }}
              >
                <h3 className="font-bold mb-3" style={{ color: "var(--dark)" }}>
                  Areas to Improve
                </h3>
                <ul className="space-y-2">
                  {analysis.areas_for_improvement.map((a, i) => (
                    <li key={i} className="flex gap-2 text-sm">
                      <span
                        className="material-symbols-outlined text-base"
                        style={{ color: "var(--primary)" }}
                      >
                        arrow_forward
                      </span>
                      {a}
                    </li>
                  ))}
                </ul>
              </div>
            )}
        </div>

        {analysis.vocabulary_used && analysis.vocabulary_used.length > 0 && (
          <div
            className="rounded-2xl p-6 mb-8"
            style={{
              background: "var(--white)",
              boxShadow: "0 4px 16px rgba(45,52,51,0.04)",
            }}
          >
            <h3 className="font-bold mb-3" style={{ color: "var(--dark)" }}>
              Vocabulary Reviewed
            </h3>
            <div className="flex flex-wrap gap-2">
              {analysis.vocabulary_used.map((v, i) => (
                <span
                  key={i}
                  className="bg-[#eaefee] px-3 py-1.5 rounded-lg text-sm"
                >
                  {v}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={resetSession}
            className="btn-primary px-6 py-3 rounded-xl text-sm font-medium"
          >
            New Session
          </button>
        </div>
      </div>
    );
  }

  return null;
}

function MessageBubble({ msg }) {
  const [showTranslation, setShowTranslation] = useState(false);
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
          {!isUser && showTranslation && msg.translation && (
            <p
              className="mt-2 text-xs italic"
              style={{ color: "var(--accent1)" }}
            >
              {msg.translation}
            </p>
          )}
        </div>
        {!isUser && (msg.translation || msg.audio) && (
          <div className="flex gap-2 mt-1.5 ml-2">
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
