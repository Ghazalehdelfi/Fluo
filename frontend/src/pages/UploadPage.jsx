import { useState, useRef } from "react";
import CreditIcon from "../components/CreditIcon";
import ExtractionReviewModal from "../components/modals/ExtractionReviewModal";
import { LangFlag } from "../utils.jsx";
import { Page, PageHeader, Card, Button, IconTile, IconButton, SectionTitle, Segmented } from "../components/ui/index.jsx";
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
  const [source, setSource] = useState("files"); // "files" | "text"
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [pastedText, setPastedText] = useState("");
  const [uploadResults, setUploadResults] = useState(null);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [pendingGrammar, setPendingGrammar] = useState([]);
  const [resolvingIndex, setResolvingIndex] = useState(null);
  const fileInputRef = useRef(null);
  const dropZoneRef = useRef(null);

  function addFiles(files) {
    if (files.length === 0) return;
    setSelectedFiles((prev) => {
      const seen = new Set(prev.map((f) => `${f.name}-${f.size}`));
      return [...prev, ...files.filter((f) => !seen.has(`${f.name}-${f.size}`))];
    });
  }

  function handleFileSelect(e) {
    addFiles(Array.from(e.target.files || []));
    e.target.value = "";
  }

  function handleDrop(e) {
    e.preventDefault();
    if (dropZoneRef.current) dropZoneRef.current.style.borderColor = "";
    addFiles(
      Array.from(e.dataTransfer.files).filter(
        (f) => f.type.startsWith("image/") || f.type === "application/pdf",
      ),
    );
  }

  function removeFile(index) {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
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
    const text = pastedText.trim();
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
      setPastedText("");
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

  const hasInput = source === "files" ? selectedFiles.length > 0 : pastedText.trim().length > 0;
  const ctaLabel =
    source === "files"
      ? selectedFiles.length > 1
        ? `Extract from ${selectedFiles.length} files`
        : "Extract from file"
      : "Extract from text";
  const ctaHint = !currentLanguageId
    ? "Select a language first"
    : !hasInput
      ? source === "files"
        ? "Add a PDF or image to continue"
        : "Paste some text to continue"
      : "Our AI reads your material and pulls out vocabulary and grammar for you to review before saving.";

  return (
    <Page>
      <PageHeader

        title="Upload Notes"
        subtitle="Turn your study material into vocabulary and grammar cards."
        actions={
          <Button variant="secondary" icon="quiz" onClick={() => navigate(`/${currentLanguageSlug}/placement`)}>
            Take placement test instead
          </Button>
        }
      />

      <Card padding="md" className="mb-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
          <SectionTitle className="!mb-0">What are you adding?</SectionTitle>
          <Segmented
            value={source}
            onChange={setSource}
            options={[
              { value: "files", label: "Files" },
              { value: "text", label: "Text" },
            ]}
          />
        </div>

        {source === "files" ? (
          <div className="space-y-4">
            <div
              ref={dropZoneRef}
              className="rounded-2xl border-2 border-dashed border-[rgba(172,179,178,0.45)] bg-[var(--surface-container-low)] p-8 sm:p-10 flex flex-col items-center justify-center text-center cursor-pointer transition-colors hover:border-[var(--primary)] hover:bg-white"
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                if (dropZoneRef.current) dropZoneRef.current.style.borderColor = "var(--primary)";
              }}
              onDragLeave={() => {
                if (dropZoneRef.current) dropZoneRef.current.style.borderColor = "";
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
              <IconTile icon="cloud_upload" size="lg" className="!rounded-full mb-4 !bg-white" />
              <p className="font-semibold text-[var(--dark)]">
                Drop files here, or <span className="text-[var(--primary)] underline underline-offset-2">browse</span>
              </p>
              <p className="text-sm text-[var(--accent1)] mt-1">PDF, JPG or PNG · photos of handwritten notes work too</p>
            </div>

            {selectedFiles.length > 0 && (
              <ul className="space-y-2">
                {selectedFiles.map((f, i) => (
                  <li key={`${f.name}-${i}`} className="flex items-center gap-3 rounded-xl bg-white border border-[rgba(172,179,178,0.25)] px-4 py-3">
                    <span className="material-symbols-outlined text-[var(--primary)]" style={{ fontSize: 20 }}>
                      {f.type === "application/pdf" ? "picture_as_pdf" : "image"}
                    </span>
                    <span className="flex-1 min-w-0 truncate text-sm font-medium text-[var(--dark)]">{f.name}</span>
                    <span className="text-xs text-[var(--accent1)] shrink-0">{formatSize(f.size)}</span>
                    <IconButton icon="close" label="Remove file" size={18} onClick={() => removeFile(i)} className="-mr-2" />
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            <textarea
              value={pastedText}
              onChange={(e) => setPastedText(e.target.value)}
              className="input-field w-full h-64 rounded-2xl p-5 text-sm resize-none placeholder:text-[var(--outline-variant)]"
              placeholder={`Paste ${currentLanguageName || "your"} notes, a short article, a vocabulary list — anything you're studying.`}
            />
            <div className="flex justify-between text-xs text-[var(--accent1)] px-1">
              <span>Plain text or Markdown</span>
              <span>{pastedText.trim().length.toLocaleString()} characters</span>
            </div>
          </div>
        )}

        <div className="mt-6 pt-6 border-t border-[rgba(172,179,178,0.2)] flex flex-col sm:flex-row sm:items-center gap-4">
          <p className={`text-sm flex-1 ${hasInput && currentLanguageId ? "text-[var(--accent1)]" : "text-[var(--outline-variant)]"}`}>
            {ctaHint}
          </p>
          <Button
            size="lg"
            icon="auto_fix_high"
            onClick={source === "files" ? uploadImage : uploadText}
            disabled={!hasInput || !currentLanguageId}
            className="sm:shrink-0"
          >
            {ctaLabel}
            <CreditIcon />
          </Button>
        </div>
      </Card>

      {/* Upload error banner */}
      {uploadError && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-2xl px-6 py-4 flex items-start gap-3">
          <span className="material-symbols-outlined text-red-500 shrink-0 mt-0.5" style={{ fontSize: 20 }}>
            error
          </span>
          <div className="flex-1">
            <div className="font-semibold text-sm text-red-700">Extraction failed</div>
            <div className="text-sm text-red-600 mt-0.5">{uploadError}</div>
          </div>
          <IconButton icon="close" label="Dismiss" size={18} onClick={() => setUploadError(null)} className="!text-red-400 hover:!text-red-600 hover:!bg-transparent -m-2" />
        </div>
      )}

      {/* Pending Grammar — needs user decision */}
      {pendingGrammar.length > 0 && (
        <Card>
          <div className="flex items-center gap-3 mb-2">
            <span className="material-symbols-outlined text-amber-500">help</span>
            <h3 className="text-lg font-bold text-[var(--dark)]">Grammar Review Needed</h3>
          </div>
          <p className="text-[var(--accent1)] text-sm mb-6">
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
                    <div className="font-semibold text-base mb-1 text-[var(--dark)]">
                      {item.candidate.concept_name}
                    </div>
                    {item.candidate.description && (
                      <p className="text-sm text-[var(--accent1)]">{item.candidate.description}</p>
                    )}
                    {item.candidate.examples && (
                      <p className="text-xs text-[#8a9494] mt-1 italic">{item.candidate.examples}</p>
                    )}
                  </div>
                  {/* Existing */}
                  <div className="bg-white rounded-xl p-4 border border-[#e0e7e6]">
                    <div className="text-xs font-bold text-[var(--primary)] uppercase tracking-wider mb-2 flex items-center gap-1">
                      <span>Existing card</span>
                      <span className="text-[var(--outline-variant)] font-normal ml-auto">
                        {Math.round(item.similarity * 100)}% similar
                      </span>
                    </div>
                    <div className="font-semibold text-base mb-1 text-[var(--dark)]">
                      {item.similar_card.concept_name}
                    </div>
                    {item.similar_card.description && (
                      <p className="text-sm text-[var(--accent1)]">{item.similar_card.description}</p>
                    )}
                    {item.similar_card.examples && (
                      <p className="text-xs text-[#8a9494] mt-1 italic">{item.similar_card.examples}</p>
                    )}
                  </div>
                </div>
                <div className="flex gap-3 justify-end">
                  <Button onClick={() => resolvePending(idx, "merge")} disabled={resolvingIndex === idx}>
                    {resolvingIndex === idx ? "Working…" : "Merge into existing"}
                  </Button>
                  <Button variant="secondary" onClick={() => resolvePending(idx, "create_new")} disabled={resolvingIndex === idx}>
                    {resolvingIndex === idx ? "Working…" : "Create new card"}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Extraction review modal */}
      {showReviewModal && uploadResults && (
        <ExtractionReviewModal
          results={uploadResults}
          onClose={() => setShowReviewModal(false)}
        />
      )}
    </Page>
  );
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
