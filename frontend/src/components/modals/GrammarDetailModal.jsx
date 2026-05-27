import { useState, useEffect } from "react";
import { useApp } from "../../context/AppContext";

export default function GrammarDetailModal({ grammar, onClose }) {
  const { apiFetch } = useApp();
  const [card, setCard] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCard();
  }, [grammar.id]);

  async function fetchCard() {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiFetch(`/api/grammar/${grammar.id}/detail-card`, {
        method: "POST",
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        setError(data.detail || "Failed to load grammar card");
        return;
      }
      const data = await resp.json();
      setCard(data);
    } catch (e) {
      setError("Network error — please try again");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(45,52,51,0.45)", backdropFilter: "blur(4px)" }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-[2rem] p-8"
        style={{ background: "var(--white)", boxShadow: "0 24px 64px rgba(45,52,51,0.18)" }}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-6 right-6 p-2 rounded-full transition-colors"
          style={{ color: "var(--outline-variant)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--dark)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--outline-variant)")}
        >
          <span className="material-symbols-outlined">close</span>
        </button>

        {loading && (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <div
              className="w-12 h-12 rounded-full border-4 animate-spin"
              style={{ borderColor: "var(--surface-container-high)", borderTopColor: "var(--primary)" }}
            />
            <p className="text-sm font-medium" style={{ color: "var(--accent1)" }}>
              Generating grammar card…
            </p>
          </div>
        )}

        {error && !loading && (
          <div className="py-10 text-center">
            <p className="text-sm mb-4" style={{ color: "#a83836" }}>{error}</p>
            <button onClick={fetchCard} className="btn-primary px-6 py-2 rounded-xl text-sm font-medium">
              Retry
            </button>
          </div>
        )}

        {card && !loading && (
          <div className="space-y-6">
            {/* Header */}
            <div>
              <h2 className="text-2xl font-extrabold tracking-tight" style={{ color: "var(--dark)" }}>
                {card.concept}
              </h2>
              {card.tagline && (
                <p className="mt-2 text-base" style={{ color: "var(--accent1)" }}>
                  {card.tagline}
                </p>
              )}
            </div>

            {/* Structure breakdown */}
            {card.breakdown && (
              <Section title="Structure">
                <code
                  className="block text-sm px-4 py-3 rounded-xl font-mono"
                  style={{ background: "var(--surface-container-low)", color: "var(--primary)" }}
                >
                  {card.breakdown.structure}
                </code>
                {card.breakdown.components?.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {card.breakdown.components.map((c, i) => (
                      <div key={i} className="flex gap-3 text-sm">
                        <span
                          className="shrink-0 font-semibold px-2 py-0.5 rounded-md"
                          style={{ background: "var(--primary-container)", color: "var(--primary-dim)" }}
                        >
                          {c.part}
                        </span>
                        <span style={{ color: "var(--accent1)" }}>
                          {c.role}
                          {c.from_trigger && (
                            <span className="ml-1 italic" style={{ color: "var(--outline-variant)" }}>
                              (e.g. &ldquo;{c.from_trigger}&rdquo;)
                            </span>
                          )}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </Section>
            )}

            {/* Core rules */}
            {card.core_rules?.length > 0 && (
              <Section title="Core Rules">
                <ul className="space-y-2">
                  {card.core_rules.map((rule, i) => (
                    <li key={i} className="flex gap-3 text-sm" style={{ color: "var(--dark)" }}>
                      <span style={{ color: "var(--primary)", fontWeight: 700, minWidth: "1.25rem" }}>
                        {i + 1}.
                      </span>
                      {rule}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {/* Examples */}
            {card.examples?.length > 0 && (
              <Section title="Examples">
                <div className="space-y-3">
                  {card.examples.map((ex, i) => (
                    <div
                      key={i}
                      className="rounded-xl p-4"
                      style={{ background: "var(--surface-container-low)" }}
                    >
                      <p className="font-semibold text-sm" style={{ color: "var(--dark)" }}>
                        {highlightText(ex.sentence, ex.highlight)}
                      </p>
                      {ex.translation && (
                        <p className="text-xs mt-1" style={{ color: "var(--accent1)" }}>
                          {ex.translation}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Nuances */}
            {card.nuances?.length > 0 && (
              <Section title="Nuances">
                <div className="space-y-3">
                  {card.nuances.map((n, i) => (
                    <div key={i} className="text-sm space-y-1">
                      <p style={{ color: "var(--dark)" }}>{n.observation}</p>
                      {n.example && (
                        <p className="italic" style={{ color: "var(--outline-variant)" }}>
                          {n.example}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Common errors */}
            {card.common_errors?.length > 0 && (
              <Section title="Common Errors">
                <div className="space-y-3">
                  {card.common_errors.map((err, i) => (
                    <div
                      key={i}
                      className="rounded-xl p-4 text-sm space-y-1"
                      style={{ background: "#fef2f2" }}
                    >
                      <div className="flex gap-2">
                        <span style={{ color: "#a83836", fontWeight: 700 }}>✗</span>
                        <span style={{ color: "#7f1d1d", textDecoration: "line-through" }}>{err.wrong}</span>
                      </div>
                      <div className="flex gap-2">
                        <span style={{ color: "var(--primary)", fontWeight: 700 }}>✓</span>
                        <span style={{ color: "var(--dark)" }}>{err.right}</span>
                      </div>
                      {err.why && (
                        <p className="mt-1" style={{ color: "var(--accent1)" }}>{err.why}</p>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Related concepts */}
            {card.related_concepts?.length > 0 && (
              <Section title="Related Concepts">
                <div className="flex flex-wrap gap-2">
                  {card.related_concepts.map((rc, i) => (
                    <span
                      key={i}
                      className="px-3 py-1 rounded-full text-xs font-medium"
                      style={{ background: "var(--surface-container-high)", color: "var(--accent1)" }}
                    >
                      {rc}
                    </span>
                  ))}
                </div>
              </Section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <h3
        className="text-xs uppercase tracking-[0.1em] font-bold mb-3"
        style={{ color: "var(--outline-variant)" }}
      >
        {title}
      </h3>
      {children}
    </div>
  );
}

/** Wraps the highlight text in a <mark> span if found in the sentence. */
function highlightText(sentence, highlight) {
  if (!highlight || !sentence.includes(highlight)) return sentence;
  const parts = sentence.split(highlight);
  return parts.reduce((acc, part, i) => {
    if (i === 0) return [part];
    return [
      ...acc,
      <mark
        key={i}
        style={{ background: "var(--primary-container)", color: "var(--primary-dim)", borderRadius: "0.2em", padding: "0 0.15em" }}
      >
        {highlight}
      </mark>,
      part,
    ];
  }, []);
}
