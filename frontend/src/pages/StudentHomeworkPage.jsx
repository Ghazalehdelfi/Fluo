import { useState, useEffect, useCallback } from "react";
import { useApp } from "../context/AppContext";

function CompletionBadge({ done, score }) {
  if (!done) return (
    <div className="w-5 h-5 rounded-full border-2 flex items-center justify-center" style={{ borderColor: "rgba(172,179,178,0.4)" }} />
  );
  return (
    <div className="flex items-center gap-1">
      <div className="w-5 h-5 rounded-full flex items-center justify-center" style={{ background: "rgba(34,197,94,0.15)" }}>
        <span className="material-symbols-outlined" style={{ fontSize: 12, color: "#22c55e" }}>check</span>
      </div>
      {score != null && <span className="text-xs font-semibold" style={{ color: "#22c55e" }}>{Math.round(score)}%</span>}
    </div>
  );
}

export default function StudentHomeworkPage() {
  const { navigate, fetchStudentHomework } = useApp();
  const [homework, setHomework] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const data = await fetchStudentHomework();
    setHomework(data);
    setLoading(false);
  }, [fetchStudentHomework]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 rounded-full border-4 border-t-transparent animate-spin" style={{ borderColor: "var(--primary)", borderTopColor: "transparent" }} />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold" style={{ color: "var(--dark)" }}>My Homework</h1>
        <p className="text-sm mt-1" style={{ color: "var(--accent1)" }}>{homework.length} assignment{homework.length !== 1 ? "s" : ""}</p>
      </div>

      {homework.length === 0 ? (
        <div className="text-center py-20" style={{ color: "var(--accent1)" }}>
          <span className="material-symbols-outlined" style={{ fontSize: 56 }}>assignment</span>
          <p className="mt-4 text-lg font-medium">No homework assigned yet</p>
          <p className="text-sm mt-1">Your teacher will assign work here once you're in a class</p>
        </div>
      ) : (
        <div className="space-y-3">
          {homework.map((hw) => {
            const isOverdue = hw.due_date && new Date(hw.due_date) < new Date();
            const completions = hw.completions || {};
            return (
              <div
                key={hw.id}
                onClick={() => navigate(`/homework/${hw.id}`)}
                className="rounded-2xl p-5 cursor-pointer transition-all"
                style={{ background: "var(--surface-container)" }}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 flex-wrap mb-1">
                      <h3 className="font-bold text-base" style={{ color: "var(--dark)" }}>{hw.name}</h3>
                      {hw.class_name && (
                        <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: "rgba(67,101,101,0.12)", color: "var(--primary)" }}>
                          {hw.class_name}
                        </span>
                      )}
                    </div>
                    {hw.due_date && (
                      <p className="text-xs mb-3 flex items-center gap-1" style={{ color: isOverdue ? "#ef4444" : "var(--accent1)" }}>
                        <span className="material-symbols-outlined" style={{ fontSize: 13 }}>calendar_today</span>
                        {isOverdue ? "Overdue: " : "Due: "}{new Date(hw.due_date).toLocaleDateString()}
                      </p>
                    )}
                    <div className="flex items-center gap-5 flex-wrap">
                      {[
                        { type: "flashcards", label: "Flashcards", icon: "style" },
                        { type: "grammar", label: "Grammar", icon: "spellcheck" },
                        { type: "conversation", label: "Conversation", icon: "chat" },
                      ].map(({ type, label, icon }) => (
                        <div key={type} className="flex items-center gap-1.5">
                          <span className="material-symbols-outlined" style={{ fontSize: 14, color: "var(--accent1)" }}>{icon}</span>
                          <span className="text-xs" style={{ color: "var(--accent1)" }}>{label}</span>
                          <CompletionBadge done={!!completions[type]} score={completions[type]?.score} />
                        </div>
                      ))}
                    </div>
                  </div>
                  <span className="material-symbols-outlined ml-4 shrink-0" style={{ fontSize: 18, color: "var(--accent1)" }}>chevron_right</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
