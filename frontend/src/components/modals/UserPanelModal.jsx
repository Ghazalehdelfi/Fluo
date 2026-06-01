import { useState, useEffect } from "react";
import { useApp } from "../../context/AppContext";
import { getLanguageEmoji, getLanguageSlug } from "../../utils.jsx";

export default function UserPanelModal() {
  const {
    currentUser,
    setCurrentUser,
    setShowUserPanelState,
    apiFetch,
    userLanguages,
    defaultLanguageId,
    setDefaultLanguageId,
    setCurrentLanguageId,
    setCurrentLanguageName,
    setCurrentLanguageSlug,
    nativeLanguage,
    setNativeLanguage,
    doLogout,
  } = useApp();

  const [credits, setCredits] = useState(currentUser?.credits || 0);
  const [totalCost, setTotalCost] = useState(0);
  const [nativeLangOptions, setNativeLangOptions] = useState(["English"]);
  const [selectedDefault, setSelectedDefault] = useState(
    defaultLanguageId ? String(defaultLanguageId) : "",
  );

  useEffect(() => {
    // credits are already in currentUser — only fetch usage + settings (lighter calls)
    loadSupplementalData();
  }, []);

  // Sync credits if currentUser changes externally
  useEffect(() => {
    setCredits(currentUser?.credits || 0);
  }, [currentUser?.credits]);

  async function loadSupplementalData() {
    try {
      const resp = await apiFetch("/api/billing/usage");
      if (resp.ok) {
        const data = await resp.json();
        setTotalCost(data.total_api_cost || 0);
      }
    } catch {}
    try {
      const resp = await apiFetch("/api/settings");
      if (resp.ok) {
        const data = await resp.json();
        setNativeLanguage(data.native_language);
        setNativeLangOptions(data.native_language_options || ["English"]);
      }
    } catch {}
  }

  async function saveDefaultLanguage(val) {
    const langId = val ? parseInt(val, 10) : null;
    setSelectedDefault(val);
    try {
      await apiFetch("/api/settings/default-language", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language_id: langId }),
      });
      setDefaultLanguageId(langId);
      if (langId) {
        const lang = userLanguages.find((l) => l.id === langId);
        if (lang) {
          setCurrentLanguageId(lang.id);
          setCurrentLanguageName(lang.name);
          setCurrentLanguageSlug(getLanguageSlug(lang.name));
        }
      }
    } catch {}
  }

  async function updateNativeLanguage(val) {
    setNativeLanguage(val);
    try {
      await apiFetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ native_language: val }),
      });
    } catch {}
  }

  async function buyCredits(pack) {
    try {
      const resp = await apiFetch("/api/billing/create-checkout-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pack,
          success_url: window.location.origin + "/?purchase=success",
          cancel_url: window.location.origin + "/?purchase=cancel",
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        alert(err.detail || "Could not start checkout.");
        return;
      }
      const data = await resp.json();
      if (data.checkout_url) window.location.href = data.checkout_url;
      else alert("No checkout URL returned.");
    } catch {
      alert("Network error");
    }
  }

  return (
    <div className="fixed inset-0 z-50">
      <div
        className="modal-overlay absolute inset-0"
        onClick={() => setShowUserPanelState(false)}
      />
      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div className="card rounded-2xl p-8 max-w-md w-full relative z-10">
          <h2
            className="text-xl font-semibold mb-6"
            style={{ color: "var(--dark)" }}
          >
            Account
          </h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-[#f1f4f3] rounded-xl">
              <div>
                <div className="text-xs font-bold uppercase tracking-widest mb-1 text-[#596060]">
                  Email
                </div>
                <div
                  className="text-sm font-medium"
                  style={{ color: "var(--dark)" }}
                >
                  {currentUser?.email || "—"}
                </div>
              </div>
            </div>
            <div className="p-4 bg-[#f1f4f3] rounded-xl space-y-3">
              <div>
                <div className="text-xs font-bold uppercase tracking-widest mb-1 text-[#596060]">
                  Credits Balance
                </div>
                <div
                  className="text-2xl font-semibold"
                  style={{ color: "var(--dark)" }}
                >
                  {Math.round(credits)} credits
                </div>
              </div>
              <p className="text-xs text-[#596060]">Top up your credits:</p>
              <div className="flex gap-2">
                {[
                  ["5", "$5", "100 credits"],
                  ["10", "$10", "200 credits"],
                  ["20", "$20", "400 credits"],
                ].map(([pack, price, credits]) => (
                  <button
                    key={pack}
                    onClick={() => buyCredits(pack)}
                    className="btn-primary flex-1 px-2 py-2 rounded-xl text-sm font-medium flex items-center justify-center gap-1.5"
                  >
                    <span className="font-semibold">{price}</span>
                    <span className="text-xs font-normal opacity-70">
                      {credits}
                    </span>
                  </button>
                ))}
              </div>
            </div>
            <div className="p-4 bg-[#f1f4f3] rounded-xl">
              <div className="text-xs font-bold uppercase tracking-widest mb-1 text-[#596060]">
                Default Language
              </div>
              <p className="text-xs text-[#596060] mb-2">
                Shown on the dashboard when you open the app
              </p>
              <select
                value={selectedDefault}
                onChange={(e) => saveDefaultLanguage(e.target.value)}
                className="w-full px-3 py-2 rounded-lg text-sm font-medium border border-[#acb3b2]/30 bg-white"
                style={{ color: "var(--dark)" }}
              >
                <option value="">— None —</option>
                {userLanguages.map((l) => (
                  <option key={l.id} value={String(l.id)}>
                    {getLanguageEmoji(l.name)} {l.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex space-x-3 mt-6">
            <button
              onClick={() => setShowUserPanelState(false)}
              className="btn-secondary flex-1 px-4 py-2.5 rounded-xl text-sm font-medium"
            >
              Close
            </button>
            <button
              onClick={doLogout}
              className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium text-red-600 border border-red-200 hover:bg-red-50 transition-colors"
            >
              Log Out
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
