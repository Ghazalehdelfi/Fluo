import { useState, useEffect } from "react";
import { useApp } from "../context/AppContext";
import { speakText, buildProficiencyDots } from "../utils.jsx";
import GrammarDetailModal from "../components/modals/GrammarDetailModal";

export default function LanguagePage({ section: initialSection }) {
  const {
    currentLanguageId,
    currentLanguageName,
    currentLanguageSlug,
    nativeLanguage,
    navigate,
    navigateToActiveSection,
    apiFetch,
    fetchVocabulary,
    fetchGrammar,
    fetchStats,
    invalidateCache,
    setPracticeGrammarId,
  } = useApp();

  const [section, setSection] = useState(initialSection || "vocabulary");
  const [stats, setStats] = useState({
    total_vocabulary: 0,
    total_grammar: 0,
    vocabulary_by_fluency: {},
    grammar_by_fluency: {},
  });
  const [vocabulary, setVocabulary] = useState([]);
  const [grammar, setGrammar] = useState([]);
  const [vocabFilter, setVocabFilter] = useState("all");
  const [practiceMenuOpen, setPracticeMenuOpen] = useState(false);
  const [detailGrammar, setDetailGrammar] = useState(null);

  useEffect(() => {
    setSection(initialSection || "vocabulary");
  }, [initialSection]);

  useEffect(() => {
    if (currentLanguageId) {
      loadStats();
      if (section === "vocabulary") loadVocabulary();
      if (section === "grammar") loadGrammar();
    }
  }, [currentLanguageId, section]);

  async function loadStats() {
    const data = await fetchStats(currentLanguageId);
    setStats(data);
  }

  async function loadVocabulary() {
    const data = await fetchVocabulary(currentLanguageId);
    setVocabulary(data);
  }

  async function loadGrammar() {
    const data = await fetchGrammar(currentLanguageId);
    setGrammar(data);
  }

  async function deleteVocab(id) {
    if (!confirm("Remove this word?")) return;
    try {
      await apiFetch(`/api/vocabulary/${id}`, { method: "DELETE" });
      setVocabulary((v) => v.filter((x) => x.id !== id));
      invalidateCache(currentLanguageId, "vocab", "stats", "dashboard");
      loadStats();
    } catch {}
  }

  async function deleteGrammar(id) {
    if (!confirm("Remove this grammar concept?")) return;
    try {
      await apiFetch(`/api/grammar/${id}`, { method: "DELETE" });
      setGrammar((g) => g.filter((x) => x.id !== id));
      invalidateCache(currentLanguageId, "grammar", "stats", "dashboard");
      loadStats();
    } catch {}
  }

  const vf = stats.vocabulary_by_fluency || {};
  const gf = stats.grammar_by_fluency || {};

  const filteredVocab =
    vocabFilter === "low"
      ? vocabulary.filter((v) => v.fluency_level === "low")
      : vocabulary;

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-start mb-10">
        <div>
          <h1
            className="text-4xl font-extrabold tracking-tight"
            style={{ color: "var(--dark)" }}
          >
            {currentLanguageName}
          </h1>
          <p className="mt-2 text-[#596060]">
            Manage your knowledge base and practice
          </p>
        </div>
        <div className="practice-menu">
          <button
            onClick={() => setPracticeMenuOpen((o) => !o)}
            className="btn-primary px-6 py-3 rounded-xl text-sm font-medium flex items-center gap-2"
          >
            Start Practice
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </button>
          {practiceMenuOpen && (
            <div
              className="practice-menu-dropdown"
              style={{ display: "block" }}
            >
              <div
                className="practice-menu-item"
                onClick={() => {
                  setPracticeMenuOpen(false);
                  navigate(`/${currentLanguageSlug}/practice`);
                }}
              >
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                  />
                </svg>
                <div>
                  <div className="font-medium">Practice Conversation</div>
                  <div className="text-xs" style={{ color: "var(--accent1)" }}>
                    AI-guided speaking practice
                  </div>
                </div>
              </div>
              <div
                className="practice-menu-item"
                onClick={() => {
                  setPracticeMenuOpen(false);
                  navigate(`/${currentLanguageSlug}/flashcards`);
                }}
              >
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                  />
                </svg>
                <div>
                  <div className="font-medium">Practice Vocabulary</div>
                  <div className="text-xs" style={{ color: "var(--accent1)" }}>
                    Flashcard review
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Section selector cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 mb-8">
        <div
          className={`p-4 sm:p-8 rounded-[2rem] cursor-pointer transition-all ${section === "vocabulary" ? "outline outline-2 outline-[#436565]" : ""}`}
          style={{
            background: "var(--white)",
            boxShadow: "0 8px 32px rgba(45,52,51,0.06)",
          }}
          onClick={() => navigate(`/${currentLanguageSlug}/vocabulary`)}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-5">
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center"
                style={{ background: "var(--tertiary-container)" }}
              >
                <span
                  className="material-symbols-outlined"
                  style={{ color: "#56634f", fontSize: 28 }}
                >
                  menu_book
                </span>
              </div>
              <div>
                <div
                  className="text-4xl font-extrabold tracking-tight"
                  style={{ color: "var(--dark)" }}
                >
                  {stats.total_vocabulary || 0}
                </div>
                <div className="font-medium text-[#596060]">
                  Vocabulary Items
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="fluency-low text-xs px-2.5 py-1 rounded-full font-medium">
                {vf.low || 0} low
              </span>
              <span className="fluency-medium text-xs px-2.5 py-1 rounded-full font-medium">
                {vf.medium || 0} med
              </span>
              <span className="fluency-high text-xs px-2.5 py-1 rounded-full font-medium">
                {vf.high || 0} high
              </span>
            </div>
          </div>
        </div>
        <div
          className={`p-4 sm:p-8 rounded-[2rem] cursor-pointer transition-all ${section === "grammar" ? "outline outline-2 outline-[#436565]" : ""}`}
          style={{ background: "var(--surface-container-low)" }}
          onClick={() => navigate(`/${currentLanguageSlug}/grammar`)}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-5">
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center"
                style={{ background: "var(--surface-container-high)" }}
              >
                <span
                  className="material-symbols-outlined"
                  style={{ color: "var(--primary)", fontSize: 28 }}
                >
                  school
                </span>
              </div>
              <div>
                <div
                  className="text-4xl font-extrabold tracking-tight"
                  style={{ color: "var(--dark)" }}
                >
                  {stats.total_grammar || 0}
                </div>
                <div className="font-medium text-[#596060]">
                  Grammar Concepts
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="fluency-low text-xs px-2.5 py-1 rounded-full font-medium">
                {gf.low || 0} low
              </span>
              <span className="fluency-medium text-xs px-2.5 py-1 rounded-full font-medium">
                {gf.medium || 0} med
              </span>
              <span className="fluency-high text-xs px-2.5 py-1 rounded-full font-medium">
                {gf.high || 0} high
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Vocabulary Section */}
      {section === "vocabulary" && (
        <div
          className="rounded-[2rem] p-8"
          style={{ background: "var(--surface-container-low)" }}
        >
          <div className="flex justify-between items-center mb-8 px-4">
            <h3 className="text-2xl font-bold" style={{ color: "var(--dark)" }}>
              Vocabulary
            </h3>
            <div className="flex gap-3">
              <button
                onClick={() => setVocabFilter("all")}
                className="px-6 py-2 text-sm font-semibold rounded-full transition-colors"
                style={{
                  background: vocabFilter === "all" ? "var(--white)" : "",
                  color: "var(--accent1)",
                }}
              >
                All Words
              </button>
              <button
                onClick={() => setVocabFilter("low")}
                className="px-6 py-2 text-sm font-semibold rounded-full transition-colors"
                style={{
                  background: vocabFilter === "low" ? "var(--white)" : "",
                  color: "var(--accent1)",
                }}
              >
                Needs Practice
              </button>
            </div>
          </div>
          {filteredVocab.length === 0 ? (
            <div className="p-12 text-center text-[#596060] text-sm">
              <div
                className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
                style={{ background: "var(--surface-container-high)" }}
              >
                <span
                  className="material-symbols-outlined"
                  style={{ color: "var(--accent1)", fontSize: 28 }}
                >
                  menu_book
                </span>
              </div>
              <p className="font-medium" style={{ color: "var(--dark)" }}>
                No vocabulary yet
              </p>
              <p className="mt-1">Upload some notes to get started!</p>
            </div>
          ) : (
            <>
              {/* Mobile card list */}
              <div className="lg:hidden space-y-3 px-2">
                {filteredVocab.map((v) => (
                  <div
                    key={v.id}
                    className="rounded-2xl px-4 py-4"
                    style={{
                      background:
                        v.fluency_level === "high"
                          ? "rgba(239,254,229,0.4)"
                          : "var(--white)",
                      boxShadow: "0 2px 8px rgba(45,52,51,0.05)",
                    }}
                  >
                    {/* Row 1: word + actions */}
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className="font-bold text-lg truncate"
                          style={{ color: "var(--dark)" }}
                        >
                          {v.target_word}
                        </span>
                        <button
                          onClick={() => speakText(v.target_word)}
                          className="p-1 shrink-0"
                          style={{ color: "var(--outline-variant)" }}
                        >
                          <span
                            className="material-symbols-outlined"
                            style={{ fontSize: 18 }}
                          >
                            volume_up
                          </span>
                        </button>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        {buildProficiencyDots(v.fluency_level)}
                        <button
                          onClick={() => deleteVocab(v.id)}
                          className="p-1 ml-1"
                          style={{ color: "var(--outline-variant)" }}
                        >
                          <span
                            className="material-symbols-outlined"
                            style={{ fontSize: 18 }}
                          >
                            delete
                          </span>
                        </button>
                      </div>
                    </div>
                    {/* Row 2: translation */}
                    <div className="mt-1.5">
                      <span
                        className="px-2.5 py-0.5 text-xs font-medium rounded-md"
                        style={{
                          background: "var(--surface-container-high)",
                          color: "var(--accent1)",
                        }}
                      >
                        {v.native_translation}
                      </span>
                    </div>
                    {/* Row 3: example sentence */}
                    {v.example_sentence && (
                      <p
                        className="mt-2 text-xs italic"
                        style={{ color: "var(--outline-variant)" }}
                      >
                        {v.example_sentence}
                      </p>
                    )}
                  </div>
                ))}
              </div>

              {/* Desktop table */}
              <div className="hidden lg:block overflow-x-auto">
                <table
                  className="w-full text-left"
                  style={{
                    borderCollapse: "separate",
                    borderSpacing: "0 1rem",
                  }}
                >
                  <thead>
                    <tr
                      className="text-xs uppercase tracking-[0.1em] font-bold"
                      style={{ color: "var(--accent1)" }}
                    >
                      <th className="px-6 pb-4">{currentLanguageName}</th>
                      <th className="px-6 pb-4">{nativeLanguage}</th>
                      <th className="px-6 pb-4">Context</th>
                      <th className="px-6 pb-4">Proficiency</th>
                      <th className="px-6 pb-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredVocab.map((v) => (
                      <tr
                        key={v.id}
                        style={{
                          background:
                            v.fluency_level === "high"
                              ? "rgba(239,254,229,0.3)"
                              : "var(--white)",
                          transition: "all 0.15s",
                        }}
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.transform = "translateX(4px)")
                        }
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.transform = "")
                        }
                      >
                        <td
                          className="px-6 py-5 font-bold text-lg"
                          style={{
                            borderRadius: "1rem 0 0 1rem",
                            color: "var(--dark)",
                          }}
                        >
                          {v.target_word}
                        </td>
                        <td className="px-6 py-5">
                          <span
                            className="px-3 py-1 text-xs font-medium rounded-md"
                            style={{
                              background: "var(--surface-container-high)",
                              color: "var(--accent1)",
                            }}
                          >
                            {v.native_translation}
                          </span>
                        </td>
                        <td
                          className="px-6 py-5 text-sm"
                          style={{ color: "var(--accent1)" }}
                        >
                          {v.example_sentence || ""}
                        </td>
                        <td className="px-6 py-5">
                          {buildProficiencyDots(v.fluency_level)}
                        </td>
                        <td
                          className="px-6 py-5 text-right"
                          style={{ borderRadius: "0 1rem 1rem 0" }}
                        >
                          <button
                            onClick={() => speakText(v.target_word)}
                            className="p-2 transition-colors"
                            style={{ color: "var(--outline-variant)" }}
                            onMouseEnter={(e) =>
                              (e.currentTarget.style.color = "var(--primary)")
                            }
                            onMouseLeave={(e) =>
                              (e.currentTarget.style.color =
                                "var(--outline-variant)")
                            }
                          >
                            <span className="material-symbols-outlined">
                              volume_up
                            </span>
                          </button>
                          <button
                            onClick={() => deleteVocab(v.id)}
                            className="p-2 transition-colors"
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
                              style={{ fontSize: 20 }}
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
            </>
          )}
        </div>
      )}

      {/* Grammar Section */}
      {section === "grammar" && (
        <div
          className="rounded-[2rem] p-8"
          style={{ background: "var(--surface-container-low)" }}
        >
          <div className="flex justify-between items-center mb-8 px-4">
            <h3 className="text-2xl font-bold" style={{ color: "var(--dark)" }}>
              Grammar Concepts
            </h3>
          </div>
          {grammar.length === 0 ? (
            <div className="p-12 text-center text-[#596060] text-sm">
              <div
                className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
                style={{ background: "var(--surface-container-high)" }}
              >
                <span
                  className="material-symbols-outlined"
                  style={{ color: "var(--accent1)", fontSize: 28 }}
                >
                  school
                </span>
              </div>
              <p className="font-medium" style={{ color: "var(--dark)" }}>
                No grammar concepts yet
              </p>
              <p className="mt-1">Upload some notes to get started!</p>
            </div>
          ) : (
            <div className="space-y-4">
              {grammar.map((g) => (
                <div
                  key={g.id}
                  className="rounded-2xl p-6 transition-all"
                  style={{
                    background:
                      g.fluency_level === "high"
                        ? "rgba(239,254,229,0.3)"
                        : "var(--white)",
                    boxShadow: "0 4px 16px rgba(45,52,51,0.04)",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.transform = "translateX(4px)")
                  }
                  onMouseLeave={(e) => (e.currentTarget.style.transform = "")}
                >
                  <div className="flex flex-col lg:flex-row lg:justify-between lg:items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <h3
                        className="font-bold text-lg"
                        style={{ color: "var(--dark)" }}
                      >
                        {g.concept_name}
                      </h3>
                      <p
                        className="text-sm mt-2"
                        style={{ color: "var(--accent1)" }}
                      >
                        {g.description}
                      </p>
                      {g.examples && (
                        <p
                          className="text-sm mt-3 italic"
                          style={{ color: "var(--outline-variant)" }}
                        >
                          {g.examples}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-3 lg:ml-6 shrink-0">
                      {buildProficiencyDots(g.fluency_level)}
                      <button
                        onClick={() => {
                          setPracticeGrammarId(g.id);
                          navigate(`/${currentLanguageSlug}/grammar-practice`);
                        }}
                        className="p-2 rounded-lg transition-colors"
                        title="Practice this grammar"
                        style={{ color: "#92400e", background: "#fef3c7" }}
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.background =
                            "var(--surface-container-high)")
                        }
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.background = "#fef3c7")
                        }
                      >
                        <span
                          className="material-symbols-outlined"
                          style={{ fontSize: 20 }}
                        >
                          exercise
                        </span>
                      </button>
                      <button
                        onClick={() => setDetailGrammar(g)}
                        className="p-2 rounded-lg transition-colors"
                        title="View detailed explanation"
                        style={{
                          color: "var(--primary)",
                          background: "var(--primary-container)",
                        }}
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.background =
                            "var(--surface-container-high)")
                        }
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.background =
                            "var(--primary-container)")
                        }
                      >
                        <span
                          className="material-symbols-outlined"
                          style={{ fontSize: 20 }}
                        >
                          auto_stories
                        </span>
                      </button>
                      <button
                        onClick={() => deleteGrammar(g.id)}
                        className="p-2 transition-colors"
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
                          style={{ fontSize: 20 }}
                        >
                          delete
                        </span>
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {detailGrammar && (
        <GrammarDetailModal
          grammar={detailGrammar}
          onClose={() => setDetailGrammar(null)}
        />
      )}
    </div>
  );
}
