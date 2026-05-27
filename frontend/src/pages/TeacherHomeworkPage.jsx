import { useState, useEffect, useCallback } from "react";
import { useApp } from "../context/AppContext";

function StatusDot({ count, label, icon }) {
  return (
    <div className="flex items-center gap-1.5 text-xs" style={{ color: "var(--accent1)" }}>
      <span className="material-symbols-outlined" style={{ fontSize: 14 }}>{icon}</span>
      <span>{count} {label}</span>
    </div>
  );
}

export default function TeacherHomeworkPage() {
  const { apiFetch, navigate, fetchMyHomework } = useApp();
  const [homework, setHomework] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    const data = await fetchMyHomework();
    setHomework(data);
    setLoading(false);
  }, [fetchMyHomework]);

  useEffect(() => { load(); }, [load]);

  async function deleteHomework(id) {
    if (!window.confirm("Delete this homework? This cannot be undone.")) return;
    setDeleting(id);
    try {
      const resp = await apiFetch(`/api/homework/${id}`, { method: "DELETE" });
      if (resp.ok) await load();
    } finally {
      setDeleting(null);
    }
  }

  function openDetail(hw) {
    navigate(`/teacher/homework/${hw.id}`);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 rounded-full border-4 border-t-transparent animate-spin" style={{ borderColor: "var(--primary)", borderTopColor: "transparent" }} />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold" style={{ color: "var(--dark)" }}>Homework</h1>
          <p className="text-sm mt-1" style={{ color: "var(--accent1)" }}>{homework.length} assignment{homework.length !== 1 ? "s" : ""}</p>
        </div>
        <button
          onClick={() => navigate("/teacher/homework/create")}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm text-white"
          style={{ background: "var(--primary)" }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>add</span>
          Create Homework
        </button>
      </div>

      {homework.length === 0 ? (
        <div className="text-center py-20" style={{ color: "var(--accent1)" }}>
          <span className="material-symbols-outlined" style={{ fontSize: 56 }}>assignment</span>
          <p className="mt-4 text-lg font-medium">No homework yet</p>
          <p className="text-sm mt-1">Create your first assignment for a class</p>
          <button
            onClick={() => navigate("/teacher/homework/create")}
            className="mt-6 px-6 py-2.5 rounded-xl text-sm font-semibold text-white"
            style={{ background: "var(--primary)" }}
          >
            Create Homework
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {homework.map((hw) => {
            const isOverdue = hw.due_date && new Date(hw.due_date) < new Date();
            return (
              <div
                key={hw.id}
                className="rounded-2xl p-5 transition-all cursor-pointer"
                style={{ background: "var(--surface-container)" }}
                onClick={() => openDetail(hw)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 flex-wrap">
                      <h3 className="font-bold text-base" style={{ color: "var(--dark)" }}>{hw.name}</h3>
                      {hw.class_name && (
                        <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: "rgba(67,101,101,0.12)", color: "var(--primary)" }}>
                          {hw.class_name}
                        </span>
                      )}
                    </div>
                    {hw.description && (
                      <p className="text-sm mt-1 truncate" style={{ color: "var(--accent1)" }}>{hw.description}</p>
                    )}
                    <div className="flex items-center gap-4 mt-3 flex-wrap">
                      <StatusDot count={hw.vocab_count} label="vocab" icon="translate" />
                      <StatusDot count={hw.grammar_count} label="grammar" icon="spellcheck" />
                      <StatusDot count={hw.topic_count} label="topics" icon="chat" />
                      {hw.due_date && (
                        <div className="flex items-center gap-1.5 text-xs" style={{ color: isOverdue ? "#ef4444" : "var(--accent1)" }}>
                          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>calendar_today</span>
                          <span>{isOverdue ? "Overdue: " : "Due: "}{new Date(hw.due_date).toLocaleDateString()}</span>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <button
                      onClick={(e) => { e.stopPropagation(); deleteHomework(hw.id); }}
                      disabled={deleting === hw.id}
                      className="p-2 rounded-xl transition-colors"
                      style={{ color: "var(--accent1)" }}
                      onMouseOver={(e) => (e.currentTarget.style.color = "#ef4444")}
                      onMouseOut={(e) => (e.currentTarget.style.color = "var(--accent1)")}
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
                        {deleting === hw.id ? "hourglass_empty" : "delete"}
                      </span>
                    </button>
                    <span className="material-symbols-outlined" style={{ fontSize: 18, color: "var(--accent1)" }}>chevron_right</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
