import { useState, useEffect } from "react";
import { useApp } from "../context/AppContext";
import { getLanguageSlug, LangFlag } from "../utils.jsx";
import { Page, PageHeader, Card, Button, IconTile, Eyebrow, SectionTitle, LoadingState } from "../components/ui/index.jsx";
import FluoBird from "../components/FluoBird.jsx";

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
    } catch {
      alert("Network error");
    }
  }

  // Onboarding: pick a language
  if (view === "onboarding-languages") {
    return (
      <Page>
        <div className="flex justify-center mb-6">
          <IconTile icon="translate" size="lg" tone="accent" className="!rounded-full w-20 h-20" />
        </div>
        <PageHeader
          align="center"
          title="Welcome to Fluō"
          subtitle="Choose a language to start your learning journey. You can always add more later."
        />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-5 max-w-3xl mx-auto">
          {availableLanguages.map((lang) => (
            <Card
              key={lang}
              interactive
              padding="md"
              className="text-center group"
              onClick={() => addLanguageFromOnboarding(lang)}
            >
              <div className="mb-3">
                <LangFlag name={lang} style={{ fontSize: "2.25rem" }} />
              </div>
              <div className="font-semibold text-lg text-[var(--dark)]">{lang}</div>
              <div className="mt-2 text-xs font-medium text-[var(--accent1)] group-hover:text-[var(--primary)] transition-colors">
                Start learning →
              </div>
            </Card>
          ))}
        </div>
      </Page>
    );
  }

  // Normal dashboard
  if (view === "normal" && dashData) {
    const streak = dashData.daily_streak || 0;
    const practicedToday = !!dashData.practiced_today;
    const week = dashData.week_activity || Array(7).fill(false);
    const totalVocab = dashData.total_vocab || 0;
    const byFluency = dashData.vocab_by_fluency || { high: 0, medium: 0, low: 0 };
    const needsPractice = byFluency.low || 0;

    const hour = new Date().getHours();
    const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
    const headline = practicedToday
      ? streak > 1
        ? `${streak} days and counting. You're on fire.`
        : "You've already practiced today. Nice."
      : streak > 0
        ? `Keep your ${streak}-day streak alive.`
        : `Ready for some ${currentLanguageName || "practice"} today?`;
    const nextStep = needsPractice > 0
      ? `${needsPractice} word${needsPractice === 1 ? "" : "s"} could use a review — a quick flashcard round will do it.`
      : totalVocab > 0
        ? "Your vocabulary is in great shape. Try a conversation to put it to work."
        : "Upload some notes or take the placement test to build your first word list.";

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

    const actions = [
      {
        icon: "style",
        title: "Flashcards",
        desc: needsPractice > 0 ? `Review ${needsPractice} word${needsPractice === 1 ? "" : "s"} that need practice` : "Run through your vocabulary",
        onClick: () => navigateToActiveSection("flashcards"),
        highlight: needsPractice > 0,
      },
      {
        icon: "forum",
        title: "Conversation",
        desc: "Speak with an AI tutor about a topic you choose",
        onClick: () => navigateToActiveSection("practice"),
      },
      {
        icon: "school",
        title: "Grammar drill",
        desc: `${dashData.total_grammar || 0} concept${dashData.total_grammar === 1 ? "" : "s"} ready to practice`,
        onClick: () => navigateToActiveSection("grammar-practice"),
      },
      {
        icon: "upload_file",
        title: "Add notes",
        desc: "Turn study material into new cards",
        onClick: () => navigateToActiveSection("notes"),
      },
    ];

    return (
      <Page>
        {/* Hero */}
        <Card variant="primary" className="overflow-hidden mb-6 dash-pop-in" padding="none">
          {/* Level pill pinned to the card's top-left, above the bird */}
          <div
            className="absolute top-5 left-5 sm:top-6 sm:left-6 z-20 rounded-full px-4 py-2 flex items-center gap-2"
            style={{ background: "rgba(255,255,255,0.14)", backdropFilter: "blur(8px)" }}
            title={fluencyDesc}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>trending_up</span>
            <span className="text-xs font-semibold opacity-85">Current level:</span>
            <span className="text-sm font-extrabold">{fluency}</span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 items-stretch">
            {/* Bird (left) */}
            <div className="lg:col-span-5 relative min-h-[220px] sm:min-h-[260px] order-2 lg:order-1">
              <div className="dash-hero-glow" style={{ left: "-4rem", top: "-4rem", width: "18rem", height: "18rem", background: "#fff", opacity: 0.12 }} />
              <div className="dash-hero-glow" style={{ right: "-2rem", bottom: "-6rem", width: "16rem", height: "16rem", background: "var(--tertiary-container)", opacity: 0.25 }} />
              <FluoBird className="absolute inset-0 w-full h-full p-4 sm:p-6" />
            </div>

            {/* Copy (right) */}
            <div className="lg:col-span-7 p-6 sm:p-10 lg:pl-4 relative z-10 flex flex-col justify-center order-1 lg:order-2">
              <Eyebrow className="!text-[var(--on-primary)] opacity-80 mb-3">
                {greeting}
              </Eyebrow>
              <h1 className="text-3xl sm:text-4xl lg:text-[2.75rem] font-extrabold tracking-tight leading-[1.1]">
                {headline}
              </h1>
              <p className="mt-4 text-base sm:text-lg opacity-85 max-w-lg">{nextStep}</p>
              <div className="mt-7 flex flex-wrap gap-3">
                <Button variant="inverse" size="lg" icon="style" onClick={() => navigateToActiveSection("flashcards")}>
                  {needsPractice > 0 ? "Review now" : "Flashcards"}
                </Button>
                <Button variant="outline" size="lg" icon="forum" onClick={() => navigateToActiveSection("practice")}>
                  Start a conversation
                </Button>
              </div>
              <WeekStrip week={week} streak={streak} className="mt-8" />
            </div>
          </div>
        </Card>

        {/* Next actions */}
        <SectionTitle className="px-1">Jump back in</SectionTitle>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 mb-6">
          {actions.map((a, i) => (
            <Card
              key={a.title}
              interactive
              padding="md"
              variant={a.highlight ? "accent" : "elevated"}
              className="group dash-pop-in"
              style={{ animationDelay: `${120 + i * 60}ms` }}
              onClick={a.onClick}
            >
              <div className="flex items-start justify-between">
                <IconTile icon={a.icon} tone={a.highlight ? "primary" : "tonal"} className={a.highlight ? "" : "!bg-[var(--surface-container-low)]"} />
                <span className="material-symbols-outlined text-[var(--outline-variant)] group-hover:text-[var(--primary)] group-hover:translate-x-0.5 transition-all" style={{ fontSize: 20 }}>
                  arrow_forward
                </span>
              </div>
              <div className="mt-4 font-bold text-[var(--dark)]">{a.title}</div>
              <p className="mt-1 text-sm text-[var(--accent1)]">{a.desc}</p>
            </Card>
          ))}
        </div>

        {/* Credits */}
        <Card variant="tonal" padding="md" className="dash-pop-in flex flex-col sm:flex-row sm:items-center gap-5" style={{ animationDelay: "400ms" }}>
          <IconTile icon="account_balance_wallet" className="!bg-white" />
          <div className="flex-1 min-w-0">
            <Eyebrow className="mb-0.5">Credits</Eyebrow>
            <div className="text-2xl font-extrabold tracking-tight text-[var(--dark)]">
              {Math.round(dashData.credits || 0)} <span className="text-sm font-medium text-[var(--accent1)]">available</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {[
              ["5", "$5", " + 100"],
              ["10", "$10", " + 200"],
              ["20", "$20", " + 400"],
            ].map(([pack, price, credits]) => (
              <Button key={pack} variant="secondary" size="sm" onClick={() => buyCredits(pack)} className="!bg-white">
                {price} <span className="font-normal text-[var(--accent1)]">{credits} credits</span>
              </Button>
            ))}
          </div>
        </Card>
      </Page>
    );
  }

  return <LoadingState />;
}

const DAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"];

function WeekStrip({ week, streak, className = "" }) {
  // week is oldest -> today; label days relative to today
  const todayIdx = (new Date().getDay() + 6) % 7; // Monday = 0
  return (
    <div className={`flex items-center gap-4 ${className}`}>
      <div className="flex gap-2">
        {week.map((active, i) => {
          const dayIdx = (todayIdx - (6 - i) + 7) % 7;
          const isToday = i === 6;
          return (
            <div key={i} className="flex flex-col items-center gap-1.5">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center transition-all"
                style={{
                  background: active ? "var(--on-primary)" : "rgba(255,255,255,0.12)",
                  color: active ? "var(--primary)" : "var(--on-primary)",
                  boxShadow: isToday ? "0 0 0 2px rgba(255,255,255,0.6)" : "none",
                  opacity: active || isToday ? 1 : 0.6,
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 16, fontVariationSettings: active ? "'FILL' 1" : "'FILL' 0" }}>
                  {active ? "check" : isToday ? "radio_button_unchecked" : "remove"}
                </span>
              </div>
              <span className="text-[10px] font-bold opacity-70">{DAY_LABELS[dayIdx]}</span>
            </div>
          );
        })}
      </div>
      <div className="text-sm opacity-85">
        <span className="font-bold">{week.filter(Boolean).length}/7</span> days this week
        {streak > 1 && <span className="opacity-80"> · {streak}-day streak</span>}
      </div>
    </div>
  );
}
