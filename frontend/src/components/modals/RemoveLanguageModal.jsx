import { useApp } from "../../context/AppContext";

export default function RemoveLanguageModal() {
  const {
    removeLangModal,
    setRemoveLangModal,
    showLoading,
    hideLoading,
    apiFetch,
    currentLanguageId,
    setCurrentLanguageId,
    setCurrentLanguageName,
    setCurrentLanguageSlug,
    defaultLanguageId,
    setDefaultLanguageId,
    loadLanguages,
    navigate,
  } = useApp();

  const { id, name } = removeLangModal;

  async function confirm() {
    setRemoveLangModal({ show: false, id: null, name: "" });
    showLoading("Removing language...");
    try {
      const resp = await apiFetch(`/api/languages/${id}`, { method: "DELETE" });
      if (resp.ok) {
        if (currentLanguageId === id) {
          setCurrentLanguageId(null);
          setCurrentLanguageName("");
          setCurrentLanguageSlug("");
        }
        if (defaultLanguageId === id) setDefaultLanguageId(null);
        await loadLanguages();
        navigate("/");
      } else {
        const err = await resp.json();
        alert(err.detail || "Error removing language");
      }
    } catch {
      alert("Error removing language");
    } finally {
      hideLoading();
    }
  }

  return (
    <div className="fixed inset-0 z-50">
      <div
        className="modal-overlay absolute inset-0"
        onClick={() => setRemoveLangModal({ show: false, id: null, name: "" })}
      />
      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div className="card rounded-2xl p-8 max-w-sm w-full relative z-10">
          <div className="flex items-center justify-center w-12 h-12 rounded-full bg-red-50 mb-4">
            <span
              className="material-symbols-outlined"
              style={{ color: "#ef4444", fontSize: 24 }}
            >
              warning
            </span>
          </div>
          <h2
            className="text-lg font-semibold mb-2"
            style={{ color: "var(--dark)" }}
          >
            Remove Language
          </h2>
          <p className="text-sm mb-1" style={{ color: "var(--accent1)" }}>
            Are you sure you want to remove <strong>{name}</strong>?
          </p>
          <p className="text-sm mb-6" style={{ color: "#ef4444" }}>
            This will permanently delete all vocabulary, grammar, and
            conversation history for this language.
          </p>
          <div className="flex space-x-3">
            <button
              onClick={() =>
                setRemoveLangModal({ show: false, id: null, name: "" })
              }
              className="btn-secondary flex-1 px-4 py-2.5 rounded-xl text-sm font-medium"
            >
              Cancel
            </button>
            <button
              onClick={confirm}
              className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium text-white bg-red-500 hover:bg-red-600 transition-colors"
            >
              Remove
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
