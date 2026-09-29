import { useState, useEffect, useCallback } from "react";
import { useApp } from "../context/AppContext";
import { Page, PageHeader, Card, Button, EmptyState, LoadingState } from "../components/ui/index.jsx";

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
      <Page>
        <LoadingState />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title="My Homework"
        subtitle={`${homework.length} assignment${homework.length !== 1 ? "s" : ""}`}
      />

      {homework.length === 0 ? (
        <Card>
          <EmptyState
            icon="assignment"
            title="No homework assigned yet"
            description="Your teacher will assign work here once you're in a class"
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {homework.map((hw) => {
            const isOverdue = hw.due_date && new Date(hw.due_date) < new Date();
            const completions = hw.completions || {};
            return (
              <Card key={hw.id} interactive padding="sm" className="!rounded-2xl" onClick={() => navigate(`/homework/${hw.id}`)}>
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
              </Card>
            );
          })}
        </div>
      )}
    </Page>
  );
}
