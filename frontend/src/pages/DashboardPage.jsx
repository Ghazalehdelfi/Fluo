import { useState, useEffect } from "react";
import { useApp } from "../context/AppContext";
import { getLanguageEmoji, getLanguageSlug } from "../utils.jsx";

export default function DashboardPage() {
  const {
    userLanguages,
    availableLanguages,
    currentLanguageId,
    currentLanguageName,
    currentLanguageSlug,
    navigate,
    navigateToActiveSection,
    apiFetch,
    showLoading,
    hideLoading,
    setCurrentLanguageId,
    setCurrentLanguageName,
    setCurrentLanguageSlug,
    setDefaultLanguageId,
    defaultLanguageId,
    loadLanguages,
    fetchDashboard,
    invalidateCache,
  } = useApp();

  const [view, setView] = useState("loading"); // 'onboarding-languages' | 'normal'
  const [dashData, setDashData] = useState(null);

  useEffect(() => {
    if (userLanguages.length === 0 && availableLanguages.length > 0) {
      setView("onboarding-languages");
    } else if (userLanguages.length > 0) {
      loadDashboard();
    }
  }, [currentLanguageId, userLanguages]);

  async function loadDashboard() {
    try {
      const data = await fetchDashboard(currentLanguageId);
      if (!data) return;
      const totalVocab = data.total_vocab || 0;
      const totalGrammar = data.total_grammar || 0;
      if (totalVocab === 0 && totalGrammar === 0 && currentLanguageSlug) {
        navigate(`/${currentLanguageSlug}/placement`, true);
        return;
      }
      setDashData(data);
      setView("normal");
    } catch (e) {
      console.error("Error loading dashboard:", e);
    }
  }

  async function addLanguageFromOnboarding(langName) {
    showLoading("Adding language...");
    try {
      const resp = await apiFetch("/api/languages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: langName }),
      });
      if (resp.ok) {
        const result = await resp.json();
        if (!defaultLanguageId) {
          apiFetch("/api/settings/default-language", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ language_id: result.id }),
          }).catch(() => {});
          setDefaultLanguageId(result.id);
        }
        setCurrentLanguageId(result.id);
        setCurrentLanguageName(langName);
        setCurrentLanguageSlug(getLanguageSlug(langName));
        invalidateCache(result.id);
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

  async function buyCredits() {
    try {
      const resp = await apiFetch("/api/billing/create-checkout-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
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
    } catch {
      alert("Network error");
    }
  }

  // Onboarding: pick a language
  if (view === "onboarding-languages") {
    return (
      <div>
        <div className="mb-10 text-center">
          <div
            className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6"
            style={{ background: "var(--tertiary-container)" }}
          >
            <span
              className="material-symbols-outlined"
              style={{ color: "var(--primary)", fontSize: 40 }}
            >
              translate
            </span>
          </div>
          <h1
            className="text-4xl font-extrabold tracking-tight"
            style={{ color: "var(--dark)" }}
          >
            Welcome to Fluō
          </h1>
          <p className="mt-3 text-lg text-[#596060] max-w-lg mx-auto">
            Choose a language to start your learning journey. You can always add
            more later.
          </p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-5 max-w-3xl mx-auto mb-8">
          {availableLanguages.map((lang) => (
            <div
              key={lang}
              onClick={() => addLanguageFromOnboarding(lang)}
              className="p-6 rounded-[2rem] cursor-pointer hover:shadow-lg hover:translate-y-[-2px] transition-all text-center group"
              style={{
                background: "var(--white)",
                boxShadow: "0 8px 32px rgba(45,52,51,0.06)",
              }}
            >
              <div className="text-4xl mb-3">{getLanguageEmoji(lang)}</div>
              <div
                className="font-semibold text-lg"
                style={{ color: "var(--dark)" }}
              >
                {lang}
              </div>
              <div className="mt-2 text-xs font-medium text-[#596060] group-hover:text-[#436565] transition-colors">
                Start learning →
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Normal dashboard
  if (view === "normal" && dashData) {
    const streak = dashData.daily_streak || 0;
    const streakMsg =
      streak === 0
        ? "Practice today to start your streak!"
        : streak === 1
          ? "Great start! Keep it going tomorrow."
          : `Amazing! ${streak} days in a row!`;

    const fluency = dashData.fluency_level || "—";
    const descMap = {
      Beginner: "Just getting started",
      Intermediate: "Building solid foundations",
      Advanced: "Strong command of the language",
      A1: "Beginner — basic phrases",
      A2: "Elementary — simple communication",
      B1: "Intermediate — everyday topics",
      B2: "Upper Intermediate — fluent interaction",
      C1: "Advanced — complex topics",
      C2: "Mastery — near-native fluency",
    };
    const fluencyDesc = descMap[fluency] || "Take a placement test to find out";

    return (
      <div>
        <div className="mb-8">
          <h1
            className="text-3xl sm:text-4xl font-extrabold tracking-tight"
            style={{ color: "var(--dark)" }}
          >
            {currentLanguageName
              ? `${currentLanguageName} Dashboard`
              : "Welcome Back"}
          </h1>
          <p className="mt-2 text-[#596060]">
            {currentLanguageName
              ? `Your ${currentLanguageName} learning overview`
              : "Your learning overview at a glance"}
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-12 gap-4 sm:gap-6 mb-8">
          {/* Credits */}
          <div
            className="col-span-1 sm:col-span-6 p-6 sm:p-8 rounded-[2rem] relative overflow-hidden flex flex-col justify-between"
            style={{
              background: "var(--primary)",
              color: "var(--on-primary)",
              minHeight: "13rem",
            }}
          >
            <div style={{ position: "relative", zIndex: 10 }}>
              <div
                className="w-12 h-12 rounded-2xl flex items-center justify-center mb-4"
                style={{ background: "rgba(255,255,255,0.15)" }}
              >
                <span
                  className="material-symbols-outlined"
                  style={{ color: "var(--on-primary)" }}
                >
                  account_balance_wallet
                </span>
              </div>
              <p
                className="text-xs font-bold uppercase tracking-widest mb-1"
                style={{ opacity: 0.8 }}
              >
                Credits Balance
              </p>
              <div className="text-5xl font-extrabold tracking-tight">
                ${(dashData.credits || 0).toFixed(2)}
              </div>
            </div>
            <div className="mt-6" style={{ position: "relative", zIndex: 10 }}>
              <button
                onClick={buyCredits}
                className="py-3 px-6 rounded-xl font-bold text-sm tracking-wide transition-all active:scale-95"
                style={{
                  background: "var(--on-primary)",
                  color: "var(--primary)",
                }}
              >
                Add Credits
              </button>
            </div>
            <div
              style={{
                position: "absolute",
                right: "-3rem",
                bottom: "-3rem",
                width: "12rem",
                height: "12rem",
                background: "white",
                opacity: 0.08,
                borderRadius: "50%",
                filter: "blur(48px)",
              }}
            />
          </div>

          {/* Daily Streak */}
          <div
            className="col-span-1 sm:col-span-6 p-6 sm:p-8 rounded-[2rem]"
            style={{
              background: "var(--white)",
              boxShadow: "0 8px 32px rgba(45,52,51,0.06)",
              minHeight: "13rem",
            }}
          >
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center mb-4"
              style={{ background: "#fff4e6" }}
            >
              <span
                className="material-symbols-outlined"
                style={{ color: "#e8760a" }}
              >
                local_fire_department
              </span>
            </div>
            <p className="text-xs font-bold uppercase tracking-widest mb-1 text-[#596060]">
              Daily Streak
            </p>
            <div className="flex items-baseline gap-2">
              <div
                className="text-5xl font-extrabold tracking-tight"
                style={{ color: "var(--dark)" }}
              >
                {streak}
              </div>
              <span className="text-lg font-medium text-[#596060]">days</span>
            </div>
            <p className="mt-3 text-sm text-[#596060]">{streakMsg}</p>
          </div>

          {/* Vocabulary */}
          <div
            className="col-span-1 sm:col-span-4 p-6 sm:p-8 rounded-[2rem] cursor-pointer hover:shadow-md transition-all"
            style={{
              background: "var(--white)",
              boxShadow: "0 8px 32px rgba(45,52,51,0.06)",
            }}
            onClick={() =>
              currentLanguageSlug &&
              navigate(`/${currentLanguageSlug}/vocabulary`)
            }
          >
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center mb-4"
              style={{ background: "var(--tertiary-container)" }}
            >
              <span
                className="material-symbols-outlined"
                style={{ color: "#56634f" }}
              >
                menu_book
              </span>
            </div>
            <p className="text-xs font-bold uppercase tracking-widest mb-1 text-[#596060]">
              Vocabulary
            </p>
            <div
              className="text-5xl font-extrabold tracking-tight"
              style={{ color: "var(--dark)" }}
            >
              {dashData.total_vocab || 0}
            </div>
            <p className="mt-2 text-sm text-[#596060]">words learned</p>
          </div>

          {/* Grammar */}
          <div
            className="col-span-1 sm:col-span-4 p-6 sm:p-8 rounded-[2rem] cursor-pointer hover:shadow-md transition-all"
            style={{ background: "var(--surface-container-low)" }}
            onClick={() =>
              currentLanguageSlug && navigate(`/${currentLanguageSlug}/grammar`)
            }
          >
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center mb-4"
              style={{ background: "var(--surface-container-high)" }}
            >
              <span
                className="material-symbols-outlined"
                style={{ color: "var(--primary)" }}
              >
                school
              </span>
            </div>
            <p className="text-xs font-bold uppercase tracking-widest mb-1 text-[#596060]">
              Grammar
            </p>
            <div
              className="text-5xl font-extrabold tracking-tight"
              style={{ color: "var(--dark)" }}
            >
              {dashData.total_grammar || 0}
            </div>
            <p className="mt-2 text-sm text-[#596060]">concepts studied</p>
          </div>

          {/* Fluency */}
          <div
            className="col-span-2 sm:col-span-4 p-6 sm:p-8 rounded-[2rem]"
            style={{
              background: "var(--white)",
              boxShadow: "0 8px 32px rgba(45,52,51,0.06)",
            }}
          >
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center mb-4"
              style={{ background: "#e8f5e9" }}
            >
              <span
                className="material-symbols-outlined"
                style={{ color: "#2e7d32" }}
              >
                trending_up
              </span>
            </div>
            <p className="text-xs font-bold uppercase tracking-widest mb-1 text-[#596060]">
              Fluency Level
            </p>
            <div
              className="text-3xl font-extrabold tracking-tight"
              style={{ color: "var(--dark)" }}
            >
              {fluency}
            </div>
            <p className="mt-2 text-sm text-[#596060]">{fluencyDesc}</p>
          </div>

          {/* Quick Actions */}
          <div
            className="col-span-2 sm:col-span-12 p-6 sm:p-8 rounded-[2rem] relative overflow-hidden flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
            style={{ background: "var(--primary)", color: "var(--on-primary)" }}
          >
            <div style={{ position: "relative", zIndex: 10 }}>
              <p
                className="text-sm font-bold tracking-widest uppercase mb-2"
                style={{ opacity: 0.8 }}
              >
                Quick Actions
              </p>
              <h3 className="text-xl font-bold leading-tight">
                Continue your learning journey
              </h3>
            </div>
            <div
              className="flex flex-wrap gap-3"
              style={{ position: "relative", zIndex: 10 }}
            >
              <button
                onClick={() => navigateToActiveSection("flashcards")}
                className="py-3 px-6 rounded-xl font-bold text-sm tracking-wide transition-all active:scale-95"
                style={{
                  background: "var(--on-primary)",
                  color: "var(--primary)",
                }}
              >
                Flashcards
              </button>
              <button
                onClick={() => navigateToActiveSection("practice")}
                className="py-3 px-6 rounded-xl font-bold text-sm tracking-wide transition-all active:scale-95 border border-white/30"
                style={{ color: "var(--on-primary)" }}
              >
                Practice
              </button>
              <button
                onClick={() => navigateToActiveSection("notes")}
                className="py-3 px-6 rounded-xl font-bold text-sm tracking-wide transition-all active:scale-95 border border-white/30"
                style={{ color: "var(--on-primary)" }}
              >
                Upload Notes
              </button>
            </div>
            <div
              style={{
                position: "absolute",
                right: "-3rem",
                bottom: "-3rem",
                width: "12rem",
                height: "12rem",
                background: "white",
                opacity: 0.08,
                borderRadius: "50%",
                filter: "blur(48px)",
              }}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center h-48">
      <div
        className="w-6 h-6 border-2 rounded-full animate-spin"
        style={{
          borderColor: "rgba(67,101,101,0.2)",
          borderTopColor: "var(--primary)",
        }}
      />
    </div>
  );
}
