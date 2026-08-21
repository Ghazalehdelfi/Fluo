import { useState } from "react";
import { useApp } from "../../context/AppContext";

/**
 * Popup shown after note extraction. Lists extracted vocabulary + grammar
 * with editable fields and a Save button (top) that persists edits.
 *
 * Props:
 *  - results: { vocabulary: [...], grammar: [...], vocabulary_added, grammar_added }
 *  - onClose: () => void
 */
export default function ExtractionReviewModal({ results, onClose }) {
  const { apiFetch } = useApp();
  const [vocab, setVocab] = useState(results.vocabulary || []);
  const [grammar, setGrammar] = useState(results.grammar || []);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  function updateVocab(i, field, value) {
    setVocab((prev) =>
      prev.map((v, idx) => (idx === i ? { ...v, [field]: value } : v)),
    );
    setSaved(false);
  }

  function updateGrammar(i, field, value) {
    setGrammar((prev) =>
      prev.map((g, idx) => (idx === i ? { ...g, [field]: value } : g)),
    );
    setSaved(false);
  }

  function removeVocab(i) {
    setVocab((prev) => prev.filter((_, idx) => idx !== i));
  }

  function removeGrammar(i) {
    setGrammar((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function saveAll() {
    setSaving(true);
    setError(null);
    try {
      const requests = [];
      for (const v of vocab) {
        if (!v.id) continue; // only items already persisted can be updated
        requests.push(
          apiFetch(`/api/vocabulary/${v.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              target_word: v.target_word,
              native_translation: v.native_translation,
              example_sentence: v.example_sentence,
            }),
          }).then(async (r) => {
            if (!r.ok) {
              const d = await r.json().catch(() => ({}));
              throw new Error(
                d.detail || `Failed to update "${v.target_word}"`,
              );
            }
          }),
        );
      }
      for (const g of grammar) {
        if (!g.id) continue;
        requests.push(
          apiFetch(`/api/grammar/${g.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              concept_name: g.concept_name,
              description: g.description,
              examples: g.examples,
            }),
          }).then(async (r) => {
            if (!r.ok) {
              const d = await r.json().catch(() => ({}));
              throw new Error(
                d.detail || `Failed to update "${g.concept_name}"`,
              );
            }
          }),
        );
      }
      await Promise.all(requests);
      setSaved(true);
    } catch (e) {
      setError(e.message || "Failed to save changes");
    } finally {
      setSaving(false);
    }
  }

  const inputCls =
    "w-full bg-white rounded-lg border border-[#e0e7e6] px-3 py-2 text-sm focus:ring-2 focus:ring-[#436565]/20 focus:border-[#436565]/40 outline-none transition-all";
  const labelCls =
    "block text-[10px] font-bold tracking-wider text-[#acb3b2] uppercase mb-1";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(45,52,51,0.45)", backdropFilter: "blur(4px)" }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="relative w-full max-w-3xl max-h-[90vh] rounded-[2rem] flex flex-col"
        style={{
          background: "var(--white)",
          boxShadow: "0 24px 64px rgba(45,52,51,0.18)",
        }}
      >
        {/* Sticky header with Save at the top */}
        <div className="sticky top-0 z-10 flex items-center justify-between gap-4 px-8 py-5 rounded-t-[2rem] border-b border-[#eef2f1] bg-white">
          <div>
            <h2
              className="text-xl font-extrabold tracking-tight"
              style={{ color: "var(--dark)" }}
            >
              Review Extracted Items
            </h2>
            <p className="text-xs text-[#596060] mt-0.5">
              {results.vocabulary_added ?? vocab.length} words ·{" "}
              {results.grammar_added ?? grammar.length} grammar added — edit
              anything before saving
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {saved && !error && (
              <span className="text-xs font-medium text-[#436565] flex items-center gap-1">
                <span
                  className="material-symbols-outlined"
                  style={{ fontSize: 16 }}
                >
                  check_circle
                </span>
                Saved
              </span>
            )}
            <button
              onClick={saveAll}
              disabled={saving}
              className="px-6 py-2.5 rounded-xl font-semibold text-sm transition-all disabled:opacity-50"
              style={{
                background: "var(--primary)",
                color: "var(--on-primary)",
              }}
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-full transition-colors"
              style={{ color: "var(--outline-variant)" }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.color = "var(--dark)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.color = "var(--outline-variant)")
              }
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto px-8 py-6 space-y-8">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
              {error}
            </div>
          )}

          {/* Vocabulary */}
          <section>
            <h3
              className="text-sm font-bold tracking-wider uppercase mb-3 flex items-center gap-2"
              style={{ color: "var(--primary)" }}
            >
              <span
                className="material-symbols-outlined"
                style={{ fontSize: 18 }}
              >
                dictionary
              </span>
              Vocabulary ({vocab.length})
            </h3>
            {vocab.length === 0 ? (
              <p className="text-sm text-[#596060]">No vocabulary extracted.</p>
            ) : (
              <div className="space-y-3">
                {vocab.map((v, i) => (
                  <div
                    key={v.id ?? i}
                    className="bg-[#f7f9f8] rounded-2xl p-4 relative group"
                  >
                    <button
                      onClick={() => removeVocab(i)}
                      title="Remove from list"
                      className="absolute top-3 right-3 p-1 rounded-full text-[#acb3b2] hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"
                    >
                      <span
                        className="material-symbols-outlined"
                        style={{ fontSize: 18 }}
                      >
                        delete
                      </span>
                    </button>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pr-8">
                      <div>
                        <label className={labelCls}>Word</label>
                        <input
                          className={inputCls}
                          value={v.target_word || ""}
                          onChange={(e) =>
                            updateVocab(i, "target_word", e.target.value)
                          }
                        />
                      </div>
                      <div>
                        <label className={labelCls}>Translation</label>
                        <input
                          className={inputCls}
                          value={v.native_translation || ""}
                          onChange={(e) =>
                            updateVocab(i, "native_translation", e.target.value)
                          }
                        />
                      </div>
                      <div className="md:col-span-2">
                        <label className={labelCls}>Example sentence</label>
                        <input
                          className={inputCls}
                          value={v.example_sentence || ""}
                          onChange={(e) =>
                            updateVocab(i, "example_sentence", e.target.value)
                          }
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Grammar */}
          <section>
            <h3
              className="text-sm font-bold tracking-wider uppercase mb-3 flex items-center gap-2"
              style={{ color: "var(--primary)" }}
            >
              <span
                className="material-symbols-outlined"
                style={{ fontSize: 18 }}
              >
                school
              </span>
              Grammar ({grammar.length})
            </h3>
            {grammar.length === 0 ? (
              <p className="text-sm text-[#596060]">No grammar extracted.</p>
            ) : (
              <div className="space-y-3">
                {grammar.map((g, i) => (
                  <div
                    key={g.id ?? i}
                    className="bg-[#f7f9f8] rounded-2xl p-4 relative group"
                  >
                    <button
                      onClick={() => removeGrammar(i)}
                      title="Remove from list"
                      className="absolute top-3 right-3 p-1 rounded-full text-[#acb3b2] hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"
                    >
                      <span
                        className="material-symbols-outlined"
                        style={{ fontSize: 18 }}
                      >
                        delete
                      </span>
                    </button>
                    <div className="space-y-3 pr-8">
                      <div>
                        <label className={labelCls}>Concept</label>
                        <input
                          className={inputCls}
                          value={g.concept_name || ""}
                          onChange={(e) =>
                            updateGrammar(i, "concept_name", e.target.value)
                          }
                        />
                      </div>
                      <div>
                        <label className={labelCls}>Description</label>
                        <textarea
                          className={`${inputCls} resize-none`}
                          rows={2}
                          value={g.description || ""}
                          onChange={(e) =>
                            updateGrammar(i, "description", e.target.value)
                          }
                        />
                      </div>
                      <div>
                        <label className={labelCls}>Examples</label>
                        <textarea
                          className={`${inputCls} resize-none`}
                          rows={2}
                          value={g.examples || ""}
                          onChange={(e) =>
                            updateGrammar(i, "examples", e.target.value)
                          }
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
