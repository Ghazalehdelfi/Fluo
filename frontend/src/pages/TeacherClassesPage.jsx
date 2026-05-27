import { useState, useEffect, useCallback } from "react";
import { useApp } from "../context/AppContext";

function ClassCodeBadge({ code }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }
  return (
    <button
      onClick={copy}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-mono font-bold tracking-widest"
      style={{ background: "var(--surface-container)", color: "var(--primary)" }}
      title="Click to copy"
    >
      {code}
      <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
        {copied ? "check" : "content_copy"}
      </span>
    </button>
  );
}

export default function TeacherClassesPage() {
  const { apiFetch, navigate, fetchMyClasses } = useApp();
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState(null);
  const [loading, setLoading] = useState(true);

  // Create class modal
  const [showCreate, setShowCreate] = useState(false);
  const [newClassName, setNewClassName] = useState("");
  const [creating, setCreating] = useState(false);

  // Add student modal
  const [addEmail, setAddEmail] = useState("");
  const [addError, setAddError] = useState("");
  const [addingStudent, setAddingStudent] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const data = await fetchMyClasses();
    setClasses(data);
    setLoading(false);
  }, [fetchMyClasses]);

  useEffect(() => { load(); }, [load]);

  async function loadClassDetail(cls) {
    try {
      const resp = await apiFetch(`/api/classes/${cls.id}`);
      if (resp.ok) {
        const detail = await resp.json();
        setSelectedClass(detail);
      }
    } catch {}
  }

  async function createClass() {
    if (!newClassName.trim()) return;
    setCreating(true);
    try {
      const resp = await apiFetch("/api/classes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newClassName.trim() }),
      });
      if (resp.ok) {
        setShowCreate(false);
        setNewClassName("");
        await load();
      }
    } finally {
      setCreating(false);
    }
  }

  async function addStudent() {
    if (!addEmail.trim() || !selectedClass) return;
    setAddingStudent(true);
    setAddError("");
    try {
      const resp = await apiFetch(`/api/classes/${selectedClass.id}/students`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: addEmail.trim() }),
      });
      if (resp.ok) {
        setAddEmail("");
        await loadClassDetail(selectedClass);
      } else {
        const data = await resp.json();
        setAddError(data.detail || "Failed to add student");
      }
    } finally {
      setAddingStudent(false);
    }
  }

  async function removeStudent(studentId) {
    if (!selectedClass) return;
    try {
      const resp = await apiFetch(
        `/api/classes/${selectedClass.id}/students/${studentId}`,
        { method: "DELETE" }
      );
      if (resp.ok) await loadClassDetail(selectedClass);
    } catch {}
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 rounded-full border-4 border-t-transparent animate-spin" style={{ borderColor: "var(--primary)", borderTopColor: "transparent" }} />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold" style={{ color: "var(--dark)" }}>My Classes</h1>
          <p className="text-sm mt-1" style={{ color: "var(--accent1)" }}>{classes.length} class{classes.length !== 1 ? "es" : ""}</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm text-white"
          style={{ background: "var(--primary)" }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>add</span>
          New Class
        </button>
      </div>

      {classes.length === 0 ? (
        <div className="text-center py-20" style={{ color: "var(--accent1)" }}>
          <span className="material-symbols-outlined" style={{ fontSize: 56 }}>groups</span>
          <p className="mt-4 text-lg font-medium">No classes yet</p>
          <p className="text-sm mt-1">Create your first class to get started</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Class list */}
          <div className="lg:col-span-1 space-y-3">
            {classes.map((cls) => (
              <div
                key={cls.id}
                onClick={() => loadClassDetail(cls)}
                className="p-4 rounded-2xl cursor-pointer transition-all"
                style={{
                  background: selectedClass?.id === cls.id ? "var(--primary)" : "var(--surface-container)",
                  color: selectedClass?.id === cls.id ? "white" : "var(--dark)",
                }}
              >
                <p className="font-semibold">{cls.name}</p>
                <p className="text-sm mt-1 opacity-70">{cls.student_count} student{cls.student_count !== 1 ? "s" : ""}</p>
              </div>
            ))}
          </div>

          {/* Class detail */}
          <div className="lg:col-span-2">
            {selectedClass ? (
              <div className="rounded-2xl p-6" style={{ background: "var(--surface-container)" }}>
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <h2 className="text-xl font-bold" style={{ color: "var(--dark)" }}>{selectedClass.name}</h2>
                    <div className="flex items-center gap-2 mt-2">
                      <span className="text-sm" style={{ color: "var(--accent1)" }}>Class code:</span>
                      <ClassCodeBadge code={selectedClass.class_code} />
                    </div>
                  </div>
                  <button
                    onClick={() => navigate("/teacher/homework")}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-semibold"
                    style={{ background: "rgba(67,101,101,0.1)", color: "var(--primary)" }}
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>assignment</span>
                    Homework
                  </button>
                </div>

                {/* Students */}
                <div className="mb-6">
                  <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--accent1)" }}>
                    Students ({selectedClass.students?.length || 0})
                  </h3>
                  {selectedClass.students?.length === 0 ? (
                    <p className="text-sm" style={{ color: "var(--accent1)" }}>No students yet — share the class code or add by email below.</p>
                  ) : (
                    <div className="space-y-2">
                      {selectedClass.students.map((s) => (
                        <div key={s.id} className="flex items-center justify-between py-2 px-3 rounded-xl" style={{ background: "var(--surface)" }}>
                          <span className="text-sm font-medium" style={{ color: "var(--dark)" }}>{s.email}</span>
                          <button
                            onClick={() => removeStudent(s.id)}
                            className="p-1 rounded-lg transition-colors"
                            style={{ color: "var(--accent1)" }}
                            onMouseOver={(e) => (e.currentTarget.style.color = "#ef4444")}
                            onMouseOut={(e) => (e.currentTarget.style.color = "var(--accent1)")}
                          >
                            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span>
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Add student by email */}
                <div>
                  <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--accent1)" }}>Add Student by Email</h3>
                  <div className="flex gap-2">
                    <input
                      type="email"
                      value={addEmail}
                      onChange={(e) => { setAddEmail(e.target.value); setAddError(""); }}
                      onKeyDown={(e) => e.key === "Enter" && addStudent()}
                      placeholder="student@example.com"
                      className="flex-1 px-3 py-2 rounded-xl text-sm border"
                      style={{ background: "var(--surface)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }}
                    />
                    <button
                      onClick={addStudent}
                      disabled={addingStudent || !addEmail.trim()}
                      className="px-4 py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-50"
                      style={{ background: "var(--primary)" }}
                    >
                      {addingStudent ? "Adding..." : "Add"}
                    </button>
                  </div>
                  {addError && <p className="text-xs mt-2 text-red-500">{addError}</p>}
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-48 rounded-2xl" style={{ background: "var(--surface-container)", color: "var(--accent1)" }}>
                <p className="text-sm">Select a class to view details</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Create class modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.4)", backdropFilter: "blur(4px)" }}>
          <div className="w-full max-w-sm rounded-2xl p-6 shadow-2xl" style={{ background: "var(--surface)" }}>
            <h2 className="text-lg font-bold mb-4" style={{ color: "var(--dark)" }}>New Class</h2>
            <input
              type="text"
              value={newClassName}
              onChange={(e) => setNewClassName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createClass()}
              placeholder="e.g. Spanish B1 Morning Group"
              className="w-full px-3 py-2.5 rounded-xl text-sm border mb-4"
              style={{ background: "var(--surface-container)", borderColor: "rgba(172,179,178,0.3)", color: "var(--dark)" }}
              autoFocus
            />
            <div className="flex gap-3">
              <button onClick={() => { setShowCreate(false); setNewClassName(""); }} className="flex-1 py-2.5 rounded-xl text-sm font-semibold" style={{ background: "var(--surface-container)", color: "var(--accent1)" }}>
                Cancel
              </button>
              <button onClick={createClass} disabled={creating || !newClassName.trim()} className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50" style={{ background: "var(--primary)" }}>
                {creating ? "Creating..." : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
