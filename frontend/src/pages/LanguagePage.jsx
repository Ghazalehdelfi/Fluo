import { useState, useEffect } from "react";
import { useApp } from "../context/AppContext";
import { speakText, buildProficiencyDots } from "../utils.jsx";
import GrammarDetailModal from "../components/modals/GrammarDetailModal";
import {
  Page,
  PageHeader,
  Card,
  Button,
  IconTile,
  Segmented,
  EmptyState,
  LoadingState,
  SectionTitle,
} from "../components/ui/index.jsx";

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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setSection(initialSection || "vocabulary");
  }, [initialSection]);

  useEffect(() => {
    if (!currentLanguageId) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([
      loadStats(),
      section === "vocabulary" ? loadVocabulary() : loadGrammar(),
    ]).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
    };
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

  const practiceMenu = (
        <div className="practice-menu">
          <Button
            size="lg"
            iconRight="expand_more"
            onClick={() => setPracticeMenuOpen((o) => !o)}
          >
            Start Practice
          </Button>
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
  );

  const sectionCards = [
    {
      key: "vocabulary",
      icon: "menu_book",
      tone: "accent",
      count: stats.total_vocabulary || 0,
      label: "Vocabulary Items",
      fluency: vf,
    },
    {
      key: "grammar",
      icon: "school",
      tone: "tonal",
      count: stats.total_grammar || 0,
      label: "Grammar Concepts",
      fluency: gf,
    },
  ];

  return (
    <Page>
      <PageHeader
        title={currentLanguageName}
        subtitle="Manage your knowledge base and practice"
        actions={practiceMenu}
      />

      {/* Section selector cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 mb-8">
        {sectionCards.map((c) => (
          <Card
            key={c.key}
            interactive
            selected={section === c.key}
            variant={section === c.key ? "elevated" : "tonal"}
            padding="md"
            onClick={() => navigate(`/${currentLanguageSlug}/${c.key}`)}
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-4">
                <IconTile icon={c.icon} tone={c.tone} size="lg" />
                <div>
                  <div className="text-3xl font-extrabold tracking-tight text-[var(--dark)]">
                    {c.count}
                  </div>
                  <div className="text-sm font-medium text-[var(--accent1)]">{c.label}</div>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="fluency-low text-xs px-2.5 py-1 rounded-full font-medium">
                  {c.fluency.low || 0} low
                </span>
                <span className="fluency-medium text-xs px-2.5 py-1 rounded-full font-medium">
                  {c.fluency.medium || 0} med
                </span>
                <span className="fluency-high text-xs px-2.5 py-1 rounded-full font-medium">
                  {c.fluency.high || 0} high
                </span>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Vocabulary Section */}
      {section === "vocabulary" && (
        <Card variant="tonal">
          <SectionTitle
            actions={
              <Segmented
                value={vocabFilter}
                onChange={setVocabFilter}
                options={[
                  { value: "all", label: "All Words" },
                  { value: "low", label: "Needs Practice" },
                ]}
              />
            }
          >
            Vocabulary
          </SectionTitle>
          {loading ? (
            <LoadingState text="Loading vocabulary…" />
          ) : filteredVocab.length === 0 ? (
            <EmptyState
              icon="menu_book"
              title="No vocabulary yet"
              description="Upload some notes to get started!"
              action={
                <Button variant="secondary" icon="upload_file" onClick={() => navigate(`/${currentLanguageSlug}/notes`)}>
                  Upload Notes
                </Button>
              }
            />
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
        </Card>
      )}

      {/* Grammar Section */}
      {section === "grammar" && (
        <Card variant="tonal">
          <SectionTitle>Grammar Concepts</SectionTitle>
          {loading ? (
            <LoadingState text="Loading grammar…" />
          ) : grammar.length === 0 ? (
            <EmptyState
              icon="school"
              title="No grammar concepts yet"
              description="Upload some notes to get started!"
              action={
                <Button variant="secondary" icon="upload_file" onClick={() => navigate(`/${currentLanguageSlug}/notes`)}>
                  Upload Notes
                </Button>
              }
            />
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
        </Card>
      )}

      {detailGrammar && (
        <GrammarDetailModal
          grammar={detailGrammar}
          onClose={() => setDetailGrammar(null)}
        />
      )}
    </Page>
  );
}
