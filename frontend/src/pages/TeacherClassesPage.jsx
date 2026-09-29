import { useState, useEffect, useCallback } from "react";
import { useApp } from "../context/AppContext";
import { Page, PageHeader, Card, Button, EmptyState, LoadingState, SectionTitle } from "../components/ui/index.jsx";

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
      <Page>
        <LoadingState />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title="My Classes"
        subtitle={`${classes.length} class${classes.length !== 1 ? "es" : ""}`}
        actions={
          <Button icon="add" onClick={() => setShowCreate(true)}>
            New Class
          </Button>
        }
      />

      {classes.length === 0 ? (
        <Card>
          <EmptyState
            icon="groups"
            title="No classes yet"
            description="Create your first class to get started"
            action={<Button icon="add" onClick={() => setShowCreate(true)}>New Class</Button>}
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Class list */}
          <div className="lg:col-span-1 space-y-3">
            {classes.map((cls) => (
              <Card
                key={cls.id}
                interactive
                padding="sm"
                variant={selectedClass?.id === cls.id ? "primary" : "tonal"}
                className="!rounded-2xl"
                onClick={() => loadClassDetail(cls)}
              >
                <p className="font-semibold">{cls.name}</p>
                <p className="text-sm mt-1 opacity-70">{cls.student_count} student{cls.student_count !== 1 ? "s" : ""}</p>
              </Card>
            ))}
          </div>

          {/* Class detail */}
          <div className="lg:col-span-2">
            {selectedClass ? (
              <Card variant="tonal" padding="md">
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <h2 className="text-lg font-bold" style={{ color: "var(--dark)" }}>{selectedClass.name}</h2>
                    <div className="flex items-center gap-2 mt-2">
                      <span className="text-sm" style={{ color: "var(--accent1)" }}>Class code:</span>
                      <ClassCodeBadge code={selectedClass.class_code} />
                    </div>
                  </div>
                  <Button variant="secondary" size="sm" icon="assignment" onClick={() => navigate("/teacher/homework")}>
                    Homework
                  </Button>
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
                        <div key={s.id} className="flex items-center justify-between py-2 px-3 rounded-xl bg-white">
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
                      className="input-field flex-1 px-4 py-2.5 rounded-xl text-sm"
                    />
                    <Button onClick={addStudent} disabled={addingStudent || !addEmail.trim()}>
                      {addingStudent ? "Adding..." : "Add"}
                    </Button>
                  </div>
                  {addError && <p className="text-xs mt-2 text-red-500">{addError}</p>}
                </div>
              </Card>
            ) : (
              <Card variant="tonal" padding="none">
                <EmptyState icon="touch_app" title="Select a class" description="Pick a class on the left to view its students and code." />
              </Card>
            )}
          </div>
        </div>
      )}

      {/* Create class modal */}
      {showCreate && (
        <div className="modal-overlay fixed inset-0 z-50 flex items-center justify-center p-4">
          <Card padding="md" className="w-full max-w-sm shadow-2xl">
            <SectionTitle>New Class</SectionTitle>
            <input
              type="text"
              value={newClassName}
              onChange={(e) => setNewClassName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createClass()}
              placeholder="e.g. Spanish B1 Morning Group"
              className="input-field w-full px-4 py-2.5 rounded-xl text-sm mb-4"
              autoFocus
            />
            <div className="flex gap-3">
              <Button variant="secondary" className="flex-1" onClick={() => { setShowCreate(false); setNewClassName(""); }}>
                Cancel
              </Button>
              <Button className="flex-1" onClick={createClass} disabled={creating || !newClassName.trim()}>
                {creating ? "Creating..." : "Create"}
              </Button>
            </div>
          </Card>
        </div>
      )}
    </Page>
  );
}
