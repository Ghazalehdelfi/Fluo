import { useState, useEffect } from "react";
import { useApp } from "../context/AppContext";
import { Page, PageHeader, Card, Button, EmptyState, LoadingState } from "../components/ui/index.jsx";

// ── Step indicator ────────────────────────────────────────────────
function StepBar({ current, total }) {
  return (
    <div className="flex items-center gap-1 mb-8">
      {Array.from({ length: total }, (_, i) => (
        <div key={i} className="flex items-center gap-1 flex-1">
          <div
            className="h-1.5 flex-1 rounded-full transition-all"
            style={{ background: i < current ? "var(--primary)" : "rgba(172,179,178,0.3)" }}
          />
        </div>
      ))}
    </div>
  );
}

// ── Step 1: Basic info ────────────────────────────────────────────
function Step1({ form, setForm, classes, languages }) {
  return (
    <div className="space-y-5">
      <h2 className="text-xl font-bold" style={{ color: "var(--dark)" }}>Basic Information</h2>
      <div>
        <label className="block text-sm font-semibold mb-1.5" style={{ color: "var(--dark)" }}>Homework Name *</label>
        <input
          type="text"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          placeholder="e.g. Week 3 Turkish Homework"
          className="w-full px-3 py-2.5 rounded-xl text-sm border"
          style={{ background: "var(--surface-container)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }}
        />
      </div>
      <div>
        <label className="block text-sm font-semibold mb-1.5" style={{ color: "var(--dark)" }}>Assign to Class *</label>
        <select
          value={form.class_id}
          onChange={(e) => setForm((f) => ({ ...f, class_id: e.target.value }))}
          className="w-full px-3 py-2.5 rounded-xl text-sm border"
          style={{ background: "var(--surface-container)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }}
        >
          <option value="">Select a class...</option>
          {classes.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-sm font-semibold mb-1.5" style={{ color: "var(--dark)" }}>Language</label>
        <select
          value={form.language_id}
          onChange={(e) => setForm((f) => ({ ...f, language_id: e.target.value }))}
          className="w-full px-3 py-2.5 rounded-xl text-sm border"
          style={{ background: "var(--surface-container)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }}
        >
          <option value="">Select a language...</option>
          {languages.map((l) => (
            <option key={l.id} value={l.id}>{l.name}</option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-sm font-semibold mb-1.5" style={{ color: "var(--dark)" }}>Description (optional)</label>
        <textarea
          value={form.description}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          placeholder="Instructions or notes for students..."
          rows={3}
          className="w-full px-3 py-2.5 rounded-xl text-sm border resize-none"
          style={{ background: "var(--surface-container)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }}
        />
      </div>
      <div>
        <label className="block text-sm font-semibold mb-1.5" style={{ color: "var(--dark)" }}>Due Date (optional)</label>
        <input
          type="date"
          value={form.due_date}
          onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
          className="w-full px-3 py-2.5 rounded-xl text-sm border"
          style={{ background: "var(--surface-container)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }}
        />
      </div>
    </div>
  );
}

// ── Step 2: Vocabulary ────────────────────────────────────────────
function Step2({ apiFetch, form, homeworkId, attachedVocabIds, setAttachedVocabIds, attachedVocabItems, setAttachedVocabItems }) {
  const [vocab, setVocab] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!form.language_id) return;
    setLoading(true);
    apiFetch(`/api/vocabulary/${form.language_id}`)
      .then((r) => r.ok ? r.json() : [])
      .then(setVocab)
      .finally(() => setLoading(false));
  }, [form.language_id]);

  async function attachSelected() {
    if (selected.size === 0) return;
    setSaving(true);
    try {
      const resp = await apiFetch(`/api/homework/${homeworkId}/vocab-refs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vocabulary_ids: [...selected] }),
      });
      if (resp.ok) {
        const newItems = vocab.filter((v) => selected.has(v.id));
        setAttachedVocabIds((prev) => new Set([...prev, ...selected]));
        setAttachedVocabItems((prev) => [...prev, ...newItems]);
        setSelected(new Set());
      }
    } finally {
      setSaving(false);
    }
  }

  async function detach(vocabId) {
    await apiFetch(`/api/homework/${homeworkId}/vocab-refs/${vocabId}`, { method: "DELETE" });
    setAttachedVocabIds((prev) => { const s = new Set(prev); s.delete(vocabId); return s; });
    setAttachedVocabItems((prev) => prev.filter((v) => v.id !== vocabId));
  }

  function toggleSelect(id) {
    setSelected((prev) => {
      const s = new Set(prev);
      if (s.has(id)) s.delete(id); else s.add(id);
      return s;
    });
  }

  const filtered = vocab.filter(
    (v) =>
      !attachedVocabIds.has(v.id) &&
      (v.target_word.toLowerCase().includes(search.toLowerCase()) ||
        v.native_translation?.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-bold" style={{ color: "var(--dark)" }}>Vocabulary</h2>
      <p className="text-sm" style={{ color: "var(--accent1)" }}>
        Select vocab from your library. Students will get these words as flashcards.
      </p>

      {!form.language_id ? (
        <div className="py-8 text-center text-sm" style={{ color: "var(--accent1)" }}>Select a language in Step 1 first.</div>
      ) : loading ? (
        <div className="py-8 text-center text-sm" style={{ color: "var(--accent1)" }}>Loading vocabulary...</div>
      ) : (
        <>
          {attachedVocabItems.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--accent1)" }}>Attached ({attachedVocabItems.length})</p>
              <div className="space-y-1.5 max-h-40 overflow-y-auto">
                {attachedVocabItems.map((v) => (
                  <div key={v.id} className="flex items-center justify-between px-3 py-2 rounded-xl" style={{ background: "rgba(67,101,101,0.08)" }}>
                    <span className="text-sm font-medium" style={{ color: "var(--dark)" }}>
                      {v.target_word} <span style={{ color: "var(--accent1)" }}>— {v.native_translation}</span>
                    </span>
                    <button onClick={() => detach(v.id)} className="p-1 rounded" style={{ color: "var(--accent1)" }}>
                      <span className="material-symbols-outlined" style={{ fontSize: 14 }}>close</span>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <div className="flex items-center gap-2 mb-2">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search vocab..."
                className="flex-1 px-3 py-2 rounded-xl text-sm border"
                style={{ background: "var(--surface-container)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }}
              />
              {selected.size > 0 && (
                <button onClick={attachSelected} disabled={saving} className="px-3 py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-50 whitespace-nowrap" style={{ background: "var(--primary)" }}>
                  {saving ? "Adding..." : `Add ${selected.size}`}
                </button>
              )}
            </div>
            <div className="space-y-1.5 max-h-64 overflow-y-auto">
              {filtered.length === 0 ? (
                <p className="text-sm text-center py-4" style={{ color: "var(--accent1)" }}>
                  {vocab.length === 0 ? "No vocabulary in your library yet." : "No more words to add."}
                </p>
              ) : (
                filtered.map((v) => (
                  <div
                    key={v.id}
                    onClick={() => toggleSelect(v.id)}
                    className="flex items-center gap-3 px-3 py-2 rounded-xl cursor-pointer transition-all"
                    style={{ background: selected.has(v.id) ? "rgba(67,101,101,0.15)" : "var(--surface-container)" }}
                  >
                    <div
                      className="w-4 h-4 rounded border-2 flex items-center justify-center shrink-0"
                      style={{ borderColor: selected.has(v.id) ? "var(--primary)" : "rgba(172,179,178,0.5)", background: selected.has(v.id) ? "var(--primary)" : "transparent" }}
                    >
                      {selected.has(v.id) && <span className="material-symbols-outlined text-white" style={{ fontSize: 11 }}>check</span>}
                    </div>
                    <span className="text-sm font-medium" style={{ color: "var(--dark)" }}>{v.target_word}</span>
                    <span className="text-sm" style={{ color: "var(--accent1)" }}>— {v.native_translation}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ── Question editor ───────────────────────────────────────────────
function QuestionEditor({ questions, onChange }) {
  function updateQ(idx, field, val) {
    onChange(questions.map((q, i) => i === idx ? { ...q, [field]: val } : q));
  }
  function removeQ(idx) { onChange(questions.filter((_, i) => i !== idx)); }
  function addQ() {
    onChange([...questions, { question_type: "translation", question_text: "", english_prompt: "", wrong_sentence: "", correct_answer: "", explanation: "", highlighted_segments: "[]", order_index: questions.length }]);
  }

  return (
    <div className="space-y-3 mt-3">
      {questions.map((q, idx) => (
        <div key={idx} className="rounded-xl p-3 space-y-2" style={{ background: "var(--surface)" }}>
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold" style={{ color: "var(--accent1)" }}>Q{idx + 1}</span>
            <div className="flex items-center gap-2">
              <select value={q.question_type} onChange={(e) => updateQ(idx, "question_type", e.target.value)} className="text-xs px-2 py-1 rounded-lg border" style={{ background: "var(--surface-container)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }}>
                <option value="translation">Translation</option>
                <option value="correction">Error Correction</option>
              </select>
              <button onClick={() => removeQ(idx)} className="p-1 rounded" style={{ color: "var(--accent1)" }}>
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>delete</span>
              </button>
            </div>
          </div>
          <input value={q.question_text} onChange={(e) => updateQ(idx, "question_text", e.target.value)} placeholder="Question shown to student..." className="w-full px-2 py-1.5 rounded-lg text-xs border" style={{ background: "var(--surface-container)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }} />
          {q.question_type === "translation" && (
            <input value={q.english_prompt || ""} onChange={(e) => updateQ(idx, "english_prompt", e.target.value)} placeholder="English sentence to translate..." className="w-full px-2 py-1.5 rounded-lg text-xs border" style={{ background: "var(--surface-container)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }} />
          )}
          {q.question_type === "correction" && (
            <input value={q.wrong_sentence || ""} onChange={(e) => updateQ(idx, "wrong_sentence", e.target.value)} placeholder="Wrong sentence (with error)..." className="w-full px-2 py-1.5 rounded-lg text-xs border" style={{ background: "var(--surface-container)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }} />
          )}
          <input value={q.correct_answer} onChange={(e) => updateQ(idx, "correct_answer", e.target.value)} placeholder="Correct answer..." className="w-full px-2 py-1.5 rounded-lg text-xs border" style={{ background: "var(--surface-container)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }} />
          <input value={q.explanation || ""} onChange={(e) => updateQ(idx, "explanation", e.target.value)} placeholder="Explanation (optional)..." className="w-full px-2 py-1.5 rounded-lg text-xs border" style={{ background: "var(--surface-container)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }} />
        </div>
      ))}
      <button onClick={addQ} className="w-full py-2 rounded-xl text-xs font-semibold border border-dashed" style={{ borderColor: "rgba(172,179,178,0.4)", color: "var(--accent1)" }}>
        + Add Question
      </button>
    </div>
  );
}

// ── Step 3: Grammar ───────────────────────────────────────────────
function Step3({ apiFetch, form, homeworkId, attachedGrammar, setAttachedGrammar, questionsMap, setQuestionsMap }) {
  const [grammarLib, setGrammarLib] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [generating, setGenerating] = useState(null);
  const [saving, setSaving] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!form.language_id) return;
    setLoading(true);
    apiFetch(`/api/grammar/${form.language_id}`)
      .then((r) => r.ok ? r.json() : [])
      .then(setGrammarLib)
      .finally(() => setLoading(false));
  }, [form.language_id]);

  const attachedIds = new Set(attachedGrammar.map((g) => g.id));

  async function attachGrammar(g) {
    await apiFetch(`/api/homework/${homeworkId}/grammar-refs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ grammar_ids: [g.id] }),
    });
    setAttachedGrammar((prev) => [...prev, g]);
    setExpandedId(g.id);
  }

  async function detachGrammar(grammarId) {
    await apiFetch(`/api/homework/${homeworkId}/grammar-refs/${grammarId}`, { method: "DELETE" });
    setAttachedGrammar((prev) => prev.filter((g) => g.id !== grammarId));
    setQuestionsMap((prev) => { const q = { ...prev }; delete q[grammarId]; return q; });
    if (expandedId === grammarId) setExpandedId(null);
  }

  async function generateQuestions(grammarId) {
    setGenerating(grammarId);
    try {
      const resp = await apiFetch(`/api/homework/${homeworkId}/grammar/${grammarId}/generate-questions`, { method: "POST" });
      if (resp.ok) {
        const data = await resp.json();
        setQuestionsMap((prev) => ({ ...prev, [grammarId]: data.questions }));
        setExpandedId(grammarId);
      } else {
        const err = await resp.json();
        alert(err.detail || "Failed to generate questions");
      }
    } finally {
      setGenerating(null);
    }
  }

  async function saveQuestions(grammarId) {
    const qs = (questionsMap[grammarId] || []).map((q, i) => ({
      ...q,
      order_index: i,
      highlighted_segments: typeof q.highlighted_segments === "string" ? q.highlighted_segments : JSON.stringify(q.highlighted_segments || []),
    }));
    setSaving(grammarId);
    try {
      await apiFetch(`/api/homework/${homeworkId}/grammar/${grammarId}/questions`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ questions: qs }),
      });
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-bold" style={{ color: "var(--dark)" }}>Grammar Concepts</h2>
      <p className="text-sm" style={{ color: "var(--accent1)" }}>Attach concepts, generate questions with AI, edit, then save.</p>

      {!form.language_id ? (
        <div className="py-8 text-center text-sm" style={{ color: "var(--accent1)" }}>Select a language in Step 1 first.</div>
      ) : loading ? (
        <div className="py-8 text-center text-sm" style={{ color: "var(--accent1)" }}>Loading grammar...</div>
      ) : (
        <>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--accent1)" }}>Your Grammar Library</p>
            <div className="space-y-1.5 max-h-40 overflow-y-auto">
              {grammarLib.filter((g) => !attachedIds.has(g.id)).map((g) => (
                <div key={g.id} className="flex items-center justify-between px-3 py-2 rounded-xl" style={{ background: "var(--surface-container)" }}>
                  <div>
                    <span className="text-sm font-medium" style={{ color: "var(--dark)" }}>{g.concept_name}</span>
                    <span className="text-xs ml-2 px-1.5 py-0.5 rounded-full" style={{ background: "rgba(172,179,178,0.2)", color: "var(--accent1)" }}>{g.fluency_level}</span>
                  </div>
                  <button onClick={() => attachGrammar(g)} className="text-xs px-2.5 py-1 rounded-lg font-semibold" style={{ background: "rgba(67,101,101,0.1)", color: "var(--primary)" }}>Add</button>
                </div>
              ))}
              {grammarLib.filter((g) => !attachedIds.has(g.id)).length === 0 && (
                <p className="text-sm text-center py-4" style={{ color: "var(--accent1)" }}>
                  {grammarLib.length === 0 ? "No grammar concepts yet. Upload notes first." : "All concepts added."}
                </p>
              )}
            </div>
          </div>

          {attachedGrammar.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--accent1)" }}>Attached Concepts</p>
              <div className="space-y-3">
                {attachedGrammar.map((g) => {
                  const qCount = questionsMap[g.id]?.length || 0;
                  const isExpanded = expandedId === g.id;
                  return (
                    <div key={g.id} className="rounded-2xl overflow-hidden" style={{ background: "var(--surface-container)" }}>
                      <div className="flex items-center justify-between px-4 py-3">
                        <button onClick={() => setExpandedId(isExpanded ? null : g.id)} className="flex items-center gap-2 flex-1 text-left">
                          <span className="font-semibold text-sm" style={{ color: "var(--dark)" }}>{g.concept_name}</span>
                          {qCount > 0 && (
                            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(67,101,101,0.12)", color: "var(--primary)" }}>{qCount} questions</span>
                          )}
                          <span className="material-symbols-outlined ml-auto" style={{ fontSize: 16, color: "var(--accent1)", transform: isExpanded ? "rotate(180deg)" : "", transition: "transform 0.2s" }}>expand_more</span>
                        </button>
                        <button onClick={() => detachGrammar(g.id)} className="p-1 ml-2 rounded" style={{ color: "var(--accent1)" }}>
                          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span>
                        </button>
                      </div>
                      {isExpanded && (
                        <div className="px-4 pb-4">
                          <div className="flex items-center gap-2 mb-3">
                            <button onClick={() => generateQuestions(g.id)} disabled={generating === g.id} className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold" style={{ background: "rgba(67,101,101,0.1)", color: "var(--primary)" }}>
                              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>{generating === g.id ? "hourglass_empty" : "auto_awesome"}</span>
                              {generating === g.id ? "Generating..." : qCount > 0 ? "Re-generate" : "Generate Questions"}
                            </button>
                            {qCount > 0 && (
                              <button onClick={() => saveQuestions(g.id)} disabled={saving === g.id} className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-white disabled:opacity-50" style={{ background: "var(--primary)" }}>
                                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>save</span>
                                {saving === g.id ? "Saving..." : "Save Questions"}
                              </button>
                            )}
                          </div>
                          {questionsMap[g.id] && (
                            <QuestionEditor
                              questions={questionsMap[g.id]}
                              onChange={(qs) => setQuestionsMap((prev) => ({ ...prev, [g.id]: qs }))}
                            />
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Step 4: Topics ────────────────────────────────────────────────
function Step4({ apiFetch, form, homeworkId, topics, setTopics }) {
  const [clusterTopics, setClusterTopics] = useState([]);
  const [customText, setCustomText] = useState("");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    if (!form.language_id) return;
    apiFetch(`/api/topics/${form.language_id}`)
      .then((r) => r.ok ? r.json() : { clusters: [] })
      .then((data) => {
        const flat = (data.clusters || []).flatMap((c) => c.topics || [c]);
        setClusterTopics(flat);
      });
  }, [form.language_id]);

  async function addTopic(text, source = "custom", cluster_topic_id = null) {
    if (!text.trim()) return;
    setAdding(true);
    try {
      const resp = await apiFetch(`/api/homework/${homeworkId}/topics`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic_text: text, source, cluster_topic_id }),
      });
      if (resp.ok) {
        const t = await resp.json();
        setTopics((prev) => [...prev, t]);
        setCustomText("");
      }
    } finally {
      setAdding(false);
    }
  }

  async function removeTopic(id) {
    await apiFetch(`/api/homework/${homeworkId}/topics/${id}`, { method: "DELETE" });
    setTopics((prev) => prev.filter((t) => t.id !== id));
  }

  const addedTexts = new Set(topics.map((t) => t.topic_text));

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-bold" style={{ color: "var(--dark)" }}>Conversation Topics</h2>
      <p className="text-sm" style={{ color: "var(--accent1)" }}>Add topics for students to practise conversation.</p>

      {topics.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--accent1)" }}>Added Topics</p>
          <div className="space-y-1.5">
            {topics.map((t) => (
              <div key={t.id} className="flex items-center justify-between px-3 py-2.5 rounded-xl" style={{ background: "rgba(67,101,101,0.08)" }}>
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined" style={{ fontSize: 14, color: "var(--primary)" }}>{t.source === "clustered" ? "hub" : "edit"}</span>
                  <span className="text-sm" style={{ color: "var(--dark)" }}>{t.topic_text}</span>
                </div>
                <button onClick={() => removeTopic(t.id)} className="p-1 rounded" style={{ color: "var(--accent1)" }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 14 }}>close</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--accent1)" }}>Custom Topic</p>
        <div className="flex gap-2">
          <input type="text" value={customText} onChange={(e) => setCustomText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addTopic(customText)} placeholder="e.g. Ordering at a restaurant..." className="flex-1 px-3 py-2.5 rounded-xl text-sm border" style={{ background: "var(--surface-container)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }} />
          <button onClick={() => addTopic(customText)} disabled={adding || !customText.trim()} className="px-4 py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-50" style={{ background: "var(--primary)" }}>Add</button>
        </div>
      </div>

      {clusterTopics.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--accent1)" }}>Suggested Topics</p>
          <div className="space-y-1.5 max-h-52 overflow-y-auto">
            {clusterTopics.filter((t) => !addedTexts.has(t.topic || t)).map((t, i) => {
              const text = t.topic || t;
              return (
                <div key={i} className="flex items-center justify-between px-3 py-2 rounded-xl" style={{ background: "var(--surface-container)" }}>
                  <div>
                    {t.theme && <span className="text-xs mr-2 px-1.5 py-0.5 rounded-full" style={{ background: "rgba(172,179,178,0.2)", color: "var(--accent1)" }}>{t.theme}</span>}
                    <span className="text-sm" style={{ color: "var(--dark)" }}>{text}</span>
                  </div>
                  <button onClick={() => addTopic(text, "clustered", t.id)} className="text-xs px-2.5 py-1 rounded-lg font-semibold" style={{ background: "rgba(67,101,101,0.1)", color: "var(--primary)" }}>Add</button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Step 5: Review (reads from parent state — no API re-fetch) ────
function Step5({ form, attachedVocabItems, attachedGrammar, questionsMap, topics }) {
  return (
    <div className="space-y-5">
      <h2 className="text-xl font-bold" style={{ color: "var(--dark)" }}>Review & Finish</h2>
      <div className="rounded-2xl p-5 space-y-4" style={{ background: "var(--surface-container)" }}>
        <div>
          <p className="text-xs uppercase tracking-wider font-semibold" style={{ color: "var(--accent1)" }}>Homework</p>
          <p className="font-bold text-lg mt-1" style={{ color: "var(--dark)" }}>{form.name}</p>
          {form.due_date && <p className="text-sm" style={{ color: "var(--accent1)" }}>Due: {new Date(form.due_date).toLocaleDateString()}</p>}
        </div>
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Vocab Words", count: attachedVocabItems.length, icon: "translate" },
            { label: "Grammar Concepts", count: attachedGrammar.length, icon: "spellcheck" },
            { label: "Topics", count: topics.length, icon: "chat" },
          ].map((item) => (
            <div key={item.label} className="text-center py-3 px-2 rounded-xl" style={{ background: "var(--surface)" }}>
              <span className="material-symbols-outlined block mb-1" style={{ fontSize: 22, color: "var(--primary)" }}>{item.icon}</span>
              <p className="text-2xl font-bold" style={{ color: "var(--dark)" }}>{item.count}</p>
              <p className="text-xs" style={{ color: "var(--accent1)" }}>{item.label}</p>
            </div>
          ))}
        </div>
        {attachedGrammar.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--accent1)" }}>Grammar Questions</p>
            {attachedGrammar.map((g) => {
              const qCount = questionsMap[g.id]?.length || 0;
              return (
                <div key={g.id} className="flex items-center justify-between px-3 py-2 rounded-xl" style={{ background: "var(--surface)" }}>
                  <span className="text-sm" style={{ color: "var(--dark)" }}>{g.concept_name}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: qCount > 0 ? "rgba(67,101,101,0.12)" : "rgba(239,68,68,0.1)", color: qCount > 0 ? "var(--primary)" : "#ef4444" }}>
                    {qCount > 0 ? `${qCount} questions` : "No questions yet"}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────
export default function CreateHomeworkPage({ homeworkId: existingId, editMode }) {
  const { apiFetch, navigate, fetchMyClasses, userLanguages, homeworkDraft, setHomeworkDraft, clearHomeworkDraft } = useApp();
  const [classes, setClasses] = useState([]);
  const [saving, setSaving] = useState(false);

  // ── All wizard state lives in AppContext so it survives navigation ──
  const { step, homeworkId, initialLoaded, form, attachedVocabIds: _vocabIds, attachedVocabItems, attachedGrammar, questionsMap, topics } = homeworkDraft;

  // attachedVocabIds is stored as array in context (Set is not plain-object-friendly), convert here
  const attachedVocabIds = new Set(_vocabIds);

  function patchDraft(patch) { setHomeworkDraft((d) => ({ ...d, ...patch })); }

  const setStep = (val) => patchDraft({ step: typeof val === "function" ? val(homeworkDraft.step) : val });
  const setForm = (val) => patchDraft({ form: typeof val === "function" ? val(homeworkDraft.form) : val });
  const setAttachedVocabIds = (val) => {
    setHomeworkDraft((d) => {
      const next = typeof val === "function" ? val(new Set(d.attachedVocabIds)) : val;
      return { ...d, attachedVocabIds: [...next] };
    });
  };
  const setAttachedVocabItems = (val) => patchDraft({ attachedVocabItems: typeof val === "function" ? val(homeworkDraft.attachedVocabItems) : val });
  const setAttachedGrammar = (val) => patchDraft({ attachedGrammar: typeof val === "function" ? val(homeworkDraft.attachedGrammar) : val });
  const setQuestionsMap = (val) => patchDraft({ questionsMap: typeof val === "function" ? val(homeworkDraft.questionsMap) : val });
  const setTopics = (val) => patchDraft({ topics: typeof val === "function" ? val(homeworkDraft.topics) : val });

  useEffect(() => { fetchMyClasses().then(setClasses); }, []);

  // If editing a specific homework that doesn't match what's in the draft, reset and load it
  useEffect(() => {
    if (existingId && homeworkDraft.homeworkId !== existingId) {
      clearHomeworkDraft();
    }
  }, [existingId]); // eslint-disable-line

  // Load existing homework data once (edit mode, or after navigating back mid-creation)
  useEffect(() => {
    const id = existingId || homeworkId;
    if (!id || initialLoaded) return;
    apiFetch(`/api/homework/${id}`)
      .then((r) => r.ok ? r.json() : null)
      .then((hw) => {
        if (!hw) return;
        setHomeworkDraft((d) => ({
          ...d,
          homeworkId: id,
          initialLoaded: true,
          form: {
            name: hw.name || "",
            class_id: String(hw.class_id || ""),
            language_id: String(hw.language_id || ""),
            description: hw.description || "",
            due_date: hw.due_date ? hw.due_date.split("T")[0] : "",
          },
          attachedVocabIds: (hw.vocab || []).map((v) => v.id),
          attachedVocabItems: hw.vocab || [],
          attachedGrammar: hw.grammar || [],
          questionsMap: Object.fromEntries((hw.grammar || []).filter((g) => g.questions?.length > 0).map((g) => [g.id, g.questions])),
          topics: hw.topics || [],
        }));
      });
  }, [existingId, homeworkId, initialLoaded]); // eslint-disable-line

  function leaveWizard() {
    clearHomeworkDraft();
    navigate("/teacher/homework");
  }

  async function handleStep1Next() {
    if (!form.name.trim() || !form.class_id) {
      alert("Please fill in the homework name and select a class.");
      return;
    }
    setSaving(true);
    try {
      if (!homeworkId) {
        const resp = await apiFetch("/api/homework", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: form.name,
            class_id: parseInt(form.class_id),
            language_id: form.language_id ? parseInt(form.language_id) : null,
            description: form.description || null,
            due_date: form.due_date || null,
          }),
        });
        if (!resp.ok) { alert("Failed to create homework"); return; }
        const data = await resp.json();
        patchDraft({ homeworkId: data.id, initialLoaded: true, step: 2 });
      } else {
        await apiFetch(`/api/homework/${homeworkId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: form.name, description: form.description || null, due_date: form.due_date || null }),
        });
        setStep(2);
      }
    } finally {
      setSaving(false);
    }
  }

  const STEP_TITLES = ["Info", "Vocab", "Grammar", "Topics", "Review"];

  function renderStep() {
    switch (step) {
      case 1: return <Step1 form={form} setForm={setForm} classes={classes} languages={userLanguages} />;
      case 2: return <Step2 apiFetch={apiFetch} form={form} homeworkId={homeworkId} attachedVocabIds={attachedVocabIds} setAttachedVocabIds={setAttachedVocabIds} attachedVocabItems={attachedVocabItems} setAttachedVocabItems={setAttachedVocabItems} />;
      case 3: return <Step3 apiFetch={apiFetch} form={form} homeworkId={homeworkId} attachedGrammar={attachedGrammar} setAttachedGrammar={setAttachedGrammar} questionsMap={questionsMap} setQuestionsMap={setQuestionsMap} />;
      case 4: return <Step4 apiFetch={apiFetch} form={form} homeworkId={homeworkId} topics={topics} setTopics={setTopics} />;
      case 5: return <Step5 form={form} attachedVocabItems={attachedVocabItems} attachedGrammar={attachedGrammar} questionsMap={questionsMap} topics={topics} />;
      default: return null;
    }
  }

  async function handleNext() {
    if (step === 1) { await handleStep1Next(); return; }
    if (step === 5) { leaveWizard(); return; }
    setStep((s) => s + 1);
  }

  return (
    <Page>
      <PageHeader
        onBack={leaveWizard}
        title={editMode ? "Edit Homework" : "Create Homework"}
        subtitle={`Step ${step} of ${STEP_TITLES.length} · ${STEP_TITLES[step - 1]}`}
        className="!mb-6"
      />

      <div className="flex gap-2 mb-6 overflow-x-auto pb-1">
        {STEP_TITLES.map((title, i) => (
          <button
            key={i}
            onClick={() => { if (homeworkId && i + 1 !== step) setStep(i + 1); }}
            disabled={!homeworkId && i + 1 > step}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-all"
            style={{
              background: i + 1 === step ? "var(--primary)" : i + 1 < step ? "rgba(67,101,101,0.12)" : "var(--surface-container)",
              color: i + 1 === step ? "white" : i + 1 < step ? "var(--primary)" : "var(--accent1)",
            }}
          >
            {i + 1 < step && <span className="material-symbols-outlined" style={{ fontSize: 12 }}>check</span>}
            {i + 1}. {title}
          </button>
        ))}
      </div>

      <StepBar current={step} total={5} />

      <Card variant="tonal" padding="md" className="mb-6">
        {renderStep()}
      </Card>

      <div className="flex items-center justify-between">
        <Button variant="secondary" icon="arrow_back" onClick={() => step > 1 ? setStep((s) => s - 1) : leaveWizard()}>
          {step === 1 ? "Cancel" : "Back"}
        </Button>
        <Button onClick={handleNext} disabled={saving} iconRight={step < 5 && !saving ? "arrow_forward" : undefined}>
          {saving ? "Saving..." : step === 5 ? "Done" : step === 1 && !homeworkId ? "Create & Continue" : "Continue"}
        </Button>
      </div>
    </Page>
  );
}
