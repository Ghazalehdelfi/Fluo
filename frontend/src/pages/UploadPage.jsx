import { useState, useRef } from "react";
import CreditIcon from "../components/CreditIcon";
import ExtractionReviewModal from "../components/modals/ExtractionReviewModal";
import { getLanguageEmoji, LangFlag } from "../utils.jsx";
import { useApp } from "../context/AppContext.jsx";

export default function UploadPage() {
  const {
    currentLanguageId,
    currentLanguageName,
    navigate,
    currentLanguageSlug,
    apiFetch,
    showLoading,
    hideLoading,
    invalidateCache,
  } = useApp();
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploadResults, setUploadResults] = useState(null);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [pendingGrammar, setPendingGrammar] = useState([]);
  const [resolvingIndex, setResolvingIndex] = useState(null);
  const fileInputRef = useRef(null);
  const dropZoneRef = useRef(null);

  function handleFileSelect(e) {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) setSelectedFiles(files);
  }

  function handleDrop(e) {
    e.preventDefault();
    if (dropZoneRef.current) dropZoneRef.current.style.borderColor = "";
    const files = Array.from(e.dataTransfer.files).filter(
      (f) => f.type.startsWith("image/") || f.type === "application/pdf",
    );
    if (files.length > 0) setSelectedFiles(files);
  }

  async function uploadImage() {
    if (selectedFiles.length === 0 || !currentLanguageId) return;
    setUploadError(null);
    let allVocabulary = [],
      allGrammar = [],
      allPending = [],
      totalVocabAdded = 0,
      totalGrammarAdded = 0;
    try {
      for (let i = 0; i < selectedFiles.length; i++) {
        showLoading(
          `Processing file ${i + 1} of ${selectedFiles.length}: ${selectedFiles[i].name}`,
        );
        const formData = new FormData();
        formData.append("language_id", currentLanguageId);
        formData.append("files", selectedFiles[i]);
        const resp = await apiFetch("/api/upload-notes", {
          method: "POST",
          body: formData,
        });
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(
            err.detail ||
              `Failed to process ${selectedFiles[i].name} (${resp.status})`,
          );
        }
        const result = await resp.json();
        allVocabulary = allVocabulary.concat(result.vocabulary || []);
        allGrammar = allGrammar.concat(result.grammar || []);
        allPending = allPending.concat(result.grammar_pending || []);
        totalVocabAdded += result.vocabulary_added || 0;
        totalGrammarAdded += result.grammar_added || 0;
      }
      setUploadResults({
        vocabulary: allVocabulary,
        grammar: allGrammar,
        vocabulary_added: totalVocabAdded,
        grammar_added: totalGrammarAdded,
      });
      setPendingGrammar(allPending);
      setShowReviewModal(true);
      invalidateCache(currentLanguageId);
      setSelectedFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (e) {
      console.error(e);
      setUploadError(e.message || "Error processing files");
    } finally {
      hideLoading();
    }
  }

  async function uploadText() {
    const textarea = document.getElementById("upload-text-input");
    const text = textarea?.value?.trim();
    if (!text || !currentLanguageId) return;
    setUploadError(null);
    showLoading("Extracting vocabulary...");
    const formData = new FormData();
    formData.append("language_id", currentLanguageId);
    formData.append("text", text);
    try {
      const resp = await apiFetch("/api/upload-notes", {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(
          err.detail || `Failed to process text (${resp.status})`,
        );
      }
      const result = await resp.json();
      setUploadResults(result);
      setPendingGrammar(result.grammar_pending || []);
      setShowReviewModal(true);
      invalidateCache(currentLanguageId);
      if (textarea) textarea.value = "";
    } catch (e) {
      console.error(e);
      setUploadError(e.message || "Error processing text");
    } finally {
      hideLoading();
    }
  }

  async function resolvePending(index, action) {
    const item = pendingGrammar[index];
    if (!item) return;
    setResolvingIndex(index);
    try {
      const body = {
        action,
        candidate: item.candidate,
        language_id: parseInt(currentLanguageId),
        existing_id: action === "merge" ? item.similar_card.id : undefined,
      };
      const resp = await apiFetch("/api/grammar/resolve-pending", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        const err = await resp.json();
        alert(err.detail || "Error resolving grammar card");
        return;
      }
      invalidateCache(currentLanguageId);
      // Remove the resolved item from the pending list
      setPendingGrammar((prev) => prev.filter((_, i) => i !== index));
      setUploadResults((prev) =>
        prev
          ? {
              ...prev,
              grammar_added:
                (prev.grammar_added || 0) + (action === "create_new" ? 1 : 0),
            }
          : prev,
      );
    } catch (e) {
      console.error(e);
      alert("Error resolving grammar card");
    } finally {
      setResolvingIndex(null);
    }
  }

  return (
    <div className="max-w-5xl mx-auto">
      <header className="mb-12">
        <h2
          className="text-4xl font-bold tracking-tight"
          style={{ color: "var(--dark)" }}
        >
          Add to Your Knowledge Base
        </h2>
        <p className="text-[#596060] text-lg mt-2">
          Expand your lexicon by uploading documents or pasting existing study
          materials.
        </p>
      </header>

      <section className="grid grid-cols-12 gap-8">
        <div className="col-span-12 lg:col-span-7 space-y-8">
          {/* Drop Zone */}
          <div
            ref={dropZoneRef}
            className="bg-white p-12 rounded-3xl border-2 border-dashed border-[#acb3b2]/30 flex flex-col items-center justify-center text-center group cursor-pointer hover:border-[#436565]/40 transition-all"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              if (dropZoneRef.current)
                dropZoneRef.current.style.borderColor = "rgba(67,101,101,0.4)";
            }}
            onDragLeave={() => {
              if (dropZoneRef.current)
                dropZoneRef.current.style.borderColor = "";
            }}
            onDrop={handleDrop}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,application/pdf"
              className="hidden"
              multiple
              onChange={handleFileSelect}
            />
            <div className="w-20 h-20 bg-[#f1f4f3] rounded-full flex items-center justify-center mb-6 group-hover:scale-105 transition-transform">
              <span className="material-symbols-outlined text-[#436565] text-4xl">
                cloud_upload
              </span>
            </div>
            <h3
              className="text-xl font-semibold mb-2"
              style={{ color: "var(--dark)" }}
            >
              Drop your files here
            </h3>
            <p className="text-[#596060] max-w-xs mb-8">
              PDF or image (JPEG, PNG, etc.). Our AI will extract the essence of
              your learning material.
            </p>
            <button
              className="bg-[#e4e9e8] text-[#596060] px-8 py-3 rounded-full font-medium hover:bg-[#dde4e3] transition-colors"
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
            >
              Browse Files
            </button>
            {selectedFiles.length > 0 && (
              <p className="mt-4 text-sm text-[#436565] font-medium">
                {selectedFiles.length === 1
                  ? selectedFiles[0].name
                  : `${selectedFiles.length} files selected`}
              </p>
            )}
          </div>

          {/* Paste Area */}
          <div className="bg-[#f1f4f3] rounded-3xl p-8">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <span
                  className="material-symbols-outlined"
                  style={{ color: "var(--primary)" }}
                >
                  edit_note
                </span>
                <h3
                  className="font-semibold text-lg"
                  style={{ color: "var(--dark)" }}
                >
                  Paste Text Content
                </h3>
              </div>
              <span className="text-[10px] font-bold tracking-wider text-[#acb3b2] uppercase">
                Plain Text / Markdown
              </span>
            </div>
            <textarea
              id="upload-text-input"
              className="w-full h-64 bg-white rounded-2xl border-none p-6 text-sm resize-none focus:ring-2 focus:ring-[#436565]/20 transition-all placeholder:text-[#acb3b2]/60"
              placeholder="Paste your notes, articles, or vocabulary lists here..."
            />
          </div>
        </div>

        <div className="col-span-12 lg:col-span-5 space-y-8">
          {/* Target Language */}
          <div className="bg-[#f1f4f3] rounded-3xl p-8">
            <h3
              className="font-semibold text-lg mb-6 flex items-center gap-2"
              style={{ color: "var(--dark)" }}
            >
              <span
                className="material-symbols-outlined"
                style={{ color: "var(--primary)" }}
              >
                label
              </span>
              Target Language
            </h3>
            <div className="bg-white rounded-xl py-4 px-5 flex items-center gap-3">
              <span className="text-2xl">
                <LangFlag
                  name={currentLanguageName || ""}
                  style={{ fontSize: "1.5rem" }}
                />
              </span>
              <div>
                <div className="font-semibold" style={{ color: "var(--dark)" }}>
                  {currentLanguageName || "Select a language"}
                </div>
                <div className="text-xs text-[#596060]">
                  Vocabulary will be added to this language
                </div>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col gap-4">
            <button
              onClick={uploadImage}
              disabled={selectedFiles.length === 0 || !currentLanguageId}
              className="w-full py-5 rounded-2xl font-bold text-lg shadow-lg hover:shadow-xl hover:translate-y-[-2px] transition-all flex items-center justify-center gap-3 disabled:opacity-40"
              style={{
                background: "var(--primary)",
                color: "var(--on-primary)",
                boxShadow: "0 8px 24px rgba(67,101,101,0.15)",
              }}
            >
              <span className="material-symbols-outlined">auto_fix_high</span>
              Extract from File
              <CreditIcon />
            </button>
            <button
              onClick={uploadText}
              className="w-full py-4 rounded-2xl font-medium transition-all flex items-center justify-center gap-3"
              style={{
                border: "1px solid var(--outline-variant)",
                color: "var(--primary)",
              }}
            >
              <span className="material-symbols-outlined">description</span>
              Extract from Text
              <CreditIcon />
            </button>
          </div>

          {/* Placement Test card */}
          <div
            onClick={() => navigate(`/${currentLanguageSlug}/placement`)}
            className="bg-white rounded-3xl p-6 cursor-pointer hover:shadow-md transition-all group"
            style={{ boxShadow: "0 4px 16px rgba(45,52,51,0.04)" }}
          >
            <div className="flex items-center gap-4">
              <div
                className="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0"
                style={{ background: "var(--primary)" }}
              >
                <span
                  className="material-symbols-outlined"
                  style={{ color: "var(--on-primary)", fontSize: 22 }}
                >
                  check_circle
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <div
                  className="font-semibold text-sm"
                  style={{ color: "var(--dark)" }}
                >
                  Take Placement Test
                </div>
                <div className="text-xs text-[#596060] mt-0.5">
                  Determine your level and auto-generate vocabulary
                </div>
              </div>
              <span
                className="material-symbols-outlined text-[#acb3b2] group-hover:text-[#436565] transition-colors"
                style={{ fontSize: 20 }}
              >
                arrow_forward
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Pending Grammar — needs user decision */}
      {pendingGrammar.length > 0 && (
        <div className="mt-12">
          <div
            className="bg-white rounded-3xl p-8"
            style={{ boxShadow: "0 8px 32px rgba(45,52,51,0.06)" }}
          >
            <div className="flex items-center gap-3 mb-2">
              <span className="material-symbols-outlined text-amber-500">
                help
              </span>
              <h3
                className="text-2xl font-bold tracking-tight"
                style={{ color: "var(--dark)" }}
              >
                Grammar Review Needed
              </h3>
            </div>
            <p className="text-[#596060] text-sm mb-6">
              These concepts are similar to ones you already have. Choose
              whether to merge with the existing card or create a new one.
            </p>
            <div className="space-y-6">
              {pendingGrammar.map((item, idx) => (
                <div
                  key={idx}
                  className="border border-amber-200 bg-amber-50 rounded-2xl p-6"
                >
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    {/* Candidate */}
                    <div className="bg-white rounded-xl p-4 border border-amber-100">
                      <div className="text-xs font-bold text-amber-600 uppercase tracking-wider mb-2">
                        New — from your notes
                      </div>
                      <div
                        className="font-semibold text-base mb-1"
                        style={{ color: "var(--dark)" }}
                      >
                        {item.candidate.concept_name}
                      </div>
                      {item.candidate.description && (
                        <p className="text-sm text-[#596060]">
                          {item.candidate.description}
                        </p>
                      )}
                      {item.candidate.examples && (
                        <p className="text-xs text-[#8a9494] mt-1 italic">
                          {item.candidate.examples}
                        </p>
                      )}
                    </div>
                    {/* Existing */}
                    <div className="bg-white rounded-xl p-4 border border-[#e0e7e6]">
                      <div className="text-xs font-bold text-[#436565] uppercase tracking-wider mb-2 flex items-center gap-1">
                        <span>Existing card</span>
                        <span className="text-[#acb3b2] font-normal ml-auto">
                          {Math.round(item.similarity * 100)}% similar
                        </span>
                      </div>
                      <div
                        className="font-semibold text-base mb-1"
                        style={{ color: "var(--dark)" }}
                      >
                        {item.similar_card.concept_name}
                      </div>
                      {item.similar_card.description && (
                        <p className="text-sm text-[#596060]">
                          {item.similar_card.description}
                        </p>
                      )}
                      {item.similar_card.examples && (
                        <p className="text-xs text-[#8a9494] mt-1 italic">
                          {item.similar_card.examples}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-3 justify-end">
                    <button
                      onClick={() => resolvePending(idx, "merge")}
                      disabled={resolvingIndex === idx}
                      className="px-5 py-2.5 rounded-xl font-medium text-sm transition-all disabled:opacity-50"
                      style={{
                        background: "var(--primary)",
                        color: "var(--on-primary)",
                      }}
                    >
                      {resolvingIndex === idx
                        ? "Working…"
                        : "Merge into existing"}
                    </button>
                    <button
                      onClick={() => resolvePending(idx, "create_new")}
                      disabled={resolvingIndex === idx}
                      className="px-5 py-2.5 rounded-xl font-medium text-sm border transition-all disabled:opacity-50"
                      style={{
                        borderColor: "var(--outline-variant)",
                        color: "var(--primary)",
                      }}
                    >
                      {resolvingIndex === idx ? "Working…" : "Create new card"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Upload error banner */}
      {uploadError && (
        <div className="mt-8 bg-red-50 border border-red-200 rounded-2xl px-6 py-4 flex items-start gap-3">
          <span
            className="material-symbols-outlined text-red-500 shrink-0 mt-0.5"
            style={{ fontSize: 20 }}
          >
            error
          </span>
          <div className="flex-1">
            <div className="font-semibold text-sm text-red-700">
              Extraction failed
            </div>
            <div className="text-sm text-red-600 mt-0.5">{uploadError}</div>
          </div>
          <button
            onClick={() => setUploadError(null)}
            className="text-red-400 hover:text-red-600 transition-colors shrink-0"
          >
            <span
              className="material-symbols-outlined"
              style={{ fontSize: 18 }}
            >
              close
            </span>
          </button>
        </div>
      )}

      {/* Extraction review modal */}
      {showReviewModal && uploadResults && (
        <ExtractionReviewModal
          results={uploadResults}
          onClose={() => setShowReviewModal(false)}
        />
      )}
    </div>
  );
}
