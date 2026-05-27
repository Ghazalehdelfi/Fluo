import { useState } from "react";
import { useApp } from "../../context/AppContext";
import { getLanguageEmoji, getLanguageSlug } from "../../utils.jsx";

export default function AddLanguageModal() {
  const {
    availableLanguages,
    setShowAddLangModal,
    showLoading,
    hideLoading,
    apiFetch,
    setCurrentLanguageId,
    setCurrentLanguageName,
    setCurrentLanguageSlug,
    defaultLanguageId,
    setDefaultLanguageId,
    loadLanguages,
    navigate,
  } = useApp();
  const [selected, setSelected] = useState(null);

  async function addLanguage() {
    if (!selected) return;
    showLoading("Adding language...");
    try {
      const resp = await apiFetch("/api/languages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: selected }),
      });
      if (resp.ok) {
        const result = await resp.json();
        setShowAddLangModal(false);
        if (!defaultLanguageId) {
          apiFetch("/api/settings/default-language", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ language_id: result.id }),
          }).catch(() => {});
          setDefaultLanguageId(result.id);
        }
        setCurrentLanguageId(result.id);
        setCurrentLanguageName(selected);
        setCurrentLanguageSlug(getLanguageSlug(selected));
        await loadLanguages();
        navigate("/");
      } else {
        const err = await resp.json();
        alert(err.detail || "Error adding language");
      }
    } catch {
      alert("Error adding language");
    } finally {
      hideLoading();
    }
  }

  return (
    <div className="fixed inset-0 z-50">
      <div
        className="modal-overlay absolute inset-0"
        onClick={() => setShowAddLangModal(false)}
      />
      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div className="card rounded-2xl p-8 max-w-md w-full relative z-10">
          <h2
            className="text-xl font-semibold mb-2"
            style={{ color: "var(--dark)" }}
          >
            Add Language
          </h2>
          <p className="text-sm mb-6" style={{ color: "var(--accent1)" }}>
            Choose a language to learn
          </p>
          <div className="grid grid-cols-2 gap-3 mb-6">
            {availableLanguages.map((lang) => (
              <div
                key={lang}
                onClick={() => setSelected(lang)}
                className={`add-lang-option card rounded-xl p-4 text-center cursor-pointer hover:bg-[#f1f4f3] transition-all ${selected === lang ? "selected" : ""}`}
              >
                <div className="text-2xl mb-1">{getLanguageEmoji(lang)}</div>
                <div className="font-medium text-sm">{lang}</div>
              </div>
            ))}
            {availableLanguages.length === 0 && (
              <p className="text-sm text-[#596060] col-span-2 text-center py-4">
                All languages added!
              </p>
            )}
          </div>
          <div className="flex space-x-3">
            <button
              onClick={() => setShowAddLangModal(false)}
              className="btn-secondary flex-1 px-4 py-2.5 rounded-xl text-sm font-medium"
            >
              Cancel
            </button>
            <button
              onClick={addLanguage}
              disabled={!selected}
              className="btn-primary flex-1 px-4 py-2.5 rounded-xl text-sm font-medium disabled:opacity-40"
            >
              Add Language
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
