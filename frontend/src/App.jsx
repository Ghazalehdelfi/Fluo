import { useState, useEffect, useRef, useCallback } from "react";
import { AppContext } from "./context/AppContext";
import { parsePath, getLanguageSlug } from "./utils.jsx";

import AuthScreen from "./components/AuthScreen.jsx";
import LandingPage from "./pages/LandingPage.jsx";
import Sidebar from "./components/Sidebar.jsx";
import LoadingOverlay from "./components/LoadingOverlay.jsx";
import AddLanguageModal from "./components/modals/AddLanguageModal.jsx";
import RemoveLanguageModal from "./components/modals/RemoveLanguageModal.jsx";
import UserPanelModal from "./components/modals/UserPanelModal.jsx";

import DashboardPage from "./pages/DashboardPage.jsx";
import LanguagePage from "./pages/LanguagePage.jsx";
import UploadPage from "./pages/UploadPage.jsx";
import FlashcardPage from "./pages/FlashcardPage.jsx";
import PracticePage from "./pages/PracticePage.jsx";
import PlacementPage from "./pages/PlacementPage.jsx";
import GrammarPracticePage from "./pages/GrammarPracticePage.jsx";
import TeacherClassesPage from "./pages/TeacherClassesPage.jsx";
import TeacherHomeworkPage from "./pages/TeacherHomeworkPage.jsx";
import CreateHomeworkPage from "./pages/CreateHomeworkPage.jsx";
import StudentHomeworkPage from "./pages/StudentHomeworkPage.jsx";
import StudentHomeworkDetailPage from "./pages/StudentHomeworkDetailPage.jsx";

export default function App() {
  const [authToken, setAuthToken] = useState(
    () => localStorage.getItem("fluo_token") || null,
  );
  const authTokenRef = useRef(authToken);
  const [currentUser, setCurrentUser] = useState(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [authChecking, setAuthChecking] = useState(true);

  const [userLanguages, setUserLanguages] = useState([]);
  const [availableLanguages, setAvailableLanguages] = useState([]);
  const [currentLanguageId, setCurrentLanguageId] = useState(null);
  const [currentLanguageName, setCurrentLanguageName] = useState("");
  const [currentLanguageSlug, setCurrentLanguageSlug] = useState("");
  const [nativeLanguage, setNativeLanguage] = useState("English");
  const [defaultLanguageId, setDefaultLanguageId] = useState(null);
  const [userLevel, setUserLevel] = useState("A1");

  const [route, setRoute] = useState(() => parsePath(window.location.pathname));

  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState("");

  // Per-language data cache: { [langId]: { vocab?, grammar?, stats?, topics?, dashboard? } }
  const langCacheRef = useRef({});

  function getLangCache(langId) {
    if (!langCacheRef.current[langId]) langCacheRef.current[langId] = {};
    return langCacheRef.current[langId];
  }

  function invalidateCache(langId, ...keys) {
    if (!langId) return;
    if (keys.length === 0) {
      langCacheRef.current[langId] = {};
    } else {
      const c = langCacheRef.current[langId] || {};
      keys.forEach((k) => delete c[k]);
    }
  }

  const [practiceGrammarId, setPracticeGrammarId] = useState(null);
  const [pendingConversationTopic, setPendingConversationTopic] =
    useState(null);

  const [showAddLangModal, setShowAddLangModal] = useState(false);
  const [removeLangModal, setRemoveLangModal] = useState({
    show: false,
    id: null,
    name: "",
  });
  const [showUserPanel, setShowUserPanel] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const BLANK_HW_DRAFT = {
    step: 1,
    homeworkId: null,
    initialLoaded: false,
    form: {
      name: "",
      class_id: "",
      language_id: "",
      description: "",
      due_date: "",
    },
    attachedVocabIds: [],
    attachedVocabItems: [],
    attachedGrammar: [],
    questionsMap: {},
    topics: [],
  };
  const [homeworkDraft, setHomeworkDraft] = useState(BLANK_HW_DRAFT);
  function clearHomeworkDraft() {
    setHomeworkDraft({ ...BLANK_HW_DRAFT });
  }

  // Keep authTokenRef in sync
  useEffect(() => {
    authTokenRef.current = authToken;
  }, [authToken]);

  // apiFetch — adds auth header, handles 401
  const apiFetch = useCallback(async (url, options = {}) => {
    const token = authTokenRef.current;
    const headers = { ...(options.headers || {}) };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const resp = await fetch(url, { ...options, headers });
    if (resp.status === 401) {
      doLogout();
      throw new Error("Unauthorized");
    }
    return resp;
  }, []);

  function doLogin(token, user) {
    localStorage.setItem("fluo_token", token);
    setAuthToken(token);
    authTokenRef.current = token;
    setCurrentUser(user);
    setAuthenticated(true);
    setNativeLanguage(user?.native_language || "English");
    // Teachers go to their classes page on first login
    if (user?.role === "teacher") {
      setRoute({ page: "teacher-classes" });
    }
  }

  function doLogout() {
    localStorage.removeItem("fluo_token");
    setAuthToken(null);
    authTokenRef.current = null;
    setCurrentUser(null);
    setAuthenticated(false);
    setUserLanguages([]);
    setCurrentLanguageId(null);
    setCurrentLanguageName("");
    setCurrentLanguageSlug("");
    window.history.pushState({ path: "/" }, "", "/");
    setRoute({ page: "dashboard" });
  }

  function navigate(path, replace = false) {
    if (replace) {
      window.history.replaceState({ path }, "", path);
    } else {
      window.history.pushState({ path }, "", path);
    }
    setRoute(parsePath(path));
  }

  function navigateToActiveSection(section) {
    if (currentLanguageSlug) {
      navigate(`/${currentLanguageSlug}/${section}`);
    }
  }

  function showLoading(text = "Loading...") {
    setLoadingText(text);
    setLoading(true);
  }
  function hideLoading() {
    setLoading(false);
    setLoadingText("");
  }

  const loadLanguages = useCallback(async () => {
    try {
      const resp = await apiFetch("/api/languages");
      if (!resp.ok) return;
      const data = await resp.json();
      const langs = data.user_languages || data || [];
      const available = data.available_languages || [];
      setUserLanguages(langs);
      setAvailableLanguages(available);
      if (data.native_language) setNativeLanguage(data.native_language);
      if (data.default_language_id)
        setDefaultLanguageId(data.default_language_id);
      if (data.user_level) setUserLevel(data.user_level);
      if (langs.length > 0) {
        // Determine which language to show active
        const parsed = parsePath(window.location.pathname);
        const matchBySlug = parsed.langSlug
          ? langs.find((l) => getLanguageSlug(l.name) === parsed.langSlug)
          : null;
        const active = matchBySlug || langs[0];
        setCurrentLanguageId(active.id);
        setCurrentLanguageName(active.name);
        setCurrentLanguageSlug(getLanguageSlug(active.name));
      }
    } catch {}
  }, [apiFetch]);

  const fetchVocabulary = useCallback(
    async (langId) => {
      const cache = getLangCache(langId);
      if (cache.vocab) return cache.vocab;
      try {
        const resp = await apiFetch(`/api/vocabulary/${langId}`);
        if (resp.ok) {
          cache.vocab = await resp.json();
          return cache.vocab;
        }
      } catch {}
      return [];
    },
    [apiFetch],
  );

  const fetchGrammar = useCallback(
    async (langId) => {
      const cache = getLangCache(langId);
      if (cache.grammar) return cache.grammar;
      try {
        const resp = await apiFetch(`/api/grammar/${langId}`);
        if (resp.ok) {
          cache.grammar = await resp.json();
          return cache.grammar;
        }
      } catch {}
      return [];
    },
    [apiFetch],
  );

  const fetchStats = useCallback(
    async (langId) => {
      const cache = getLangCache(langId);
      if (cache.stats) return cache.stats;
      try {
        const resp = await apiFetch(`/api/stats/${langId}`);
        if (resp.ok) {
          cache.stats = await resp.json();
          return cache.stats;
        }
      } catch {}
      return {
        total_vocabulary: 0,
        total_grammar: 0,
        vocabulary_by_fluency: {},
        grammar_by_fluency: {},
      };
    },
    [apiFetch],
  );

  const fetchTopics = useCallback(
    async (langId) => {
      const cache = getLangCache(langId);
      if (cache.topics) return cache.topics;
      try {
        const resp = await apiFetch(`/api/topics/${langId}`);
        if (resp.ok) {
          cache.topics = await resp.json();
          return cache.topics;
        }
      } catch {}
      return { clusters: [] };
    },
    [apiFetch],
  );

  const fetchDashboard = useCallback(
    async (langId) => {
      const cache = getLangCache(langId);
      if (cache.dashboard) return cache.dashboard;
      try {
        const url = langId
          ? `/api/dashboard?language_id=${langId}`
          : "/api/dashboard";
        const resp = await apiFetch(url);
        if (resp.ok) {
          cache.dashboard = await resp.json();
          return cache.dashboard;
        }
      } catch {}
      return null;
    },
    [apiFetch],
  );

  const fetchMyClasses = useCallback(async () => {
    try {
      const resp = await apiFetch("/api/classes");
      if (resp.ok) return await resp.json();
    } catch {}
    return [];
  }, [apiFetch]);

  const fetchMyHomework = useCallback(async () => {
    try {
      const resp = await apiFetch("/api/homework");
      if (resp.ok) return await resp.json();
    } catch {}
    return [];
  }, [apiFetch]);

  const fetchStudentHomework = useCallback(async () => {
    try {
      const resp = await apiFetch("/api/student/homework");
      if (resp.ok) return await resp.json();
    } catch {}
    return [];
  }, [apiFetch]);

  // Check auth on mount
  useEffect(() => {
    async function checkAuth() {
      if (!authToken) {
        setAuthChecking(false);
        return;
      }
      try {
        const resp = await apiFetch("/api/user/me");
        if (resp.ok) {
          const user = await resp.json();
          setCurrentUser(user);
          setAuthenticated(true);
          setNativeLanguage(user?.native_language || "English");
          await loadLanguages();
        } else {
          doLogout();
        }
      } catch {
        doLogout();
      } finally {
        setAuthChecking(false);
      }
    }
    checkAuth();
  }, []); // eslint-disable-line

  // Load languages when authenticated
  useEffect(() => {
    if (authenticated) loadLanguages();
  }, [authenticated]);

  // Popstate (back/forward)
  useEffect(() => {
    function onPopState(e) {
      setRoute(parsePath(e.state?.path || window.location.pathname));
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  // Update active language when route changes
  useEffect(() => {
    if (route.langSlug && userLanguages.length > 0) {
      const match = userLanguages.find(
        (l) => getLanguageSlug(l.name) === route.langSlug,
      );
      if (match) {
        setCurrentLanguageId(match.id);
        setCurrentLanguageName(match.name);
        setCurrentLanguageSlug(getLanguageSlug(match.name));
      }
    }
  }, [route.langSlug, userLanguages]);

  const contextValue = {
    authToken,
    currentUser,
    userLanguages,
    availableLanguages,
    currentLanguageId,
    currentLanguageName,
    currentLanguageSlug,
    nativeLanguage,
    defaultLanguageId,
    userLevel,
    setUserLevel,
    route,
    setRoute,
    loading,
    loadingText,
    showAddLangModal,
    removeLangModal,
    showUserPanel,
    apiFetch,
    doLogin,
    doLogout,
    navigate,
    navigateToActiveSection,
    loadLanguages,
    fetchVocabulary,
    fetchGrammar,
    fetchStats,
    fetchTopics,
    fetchDashboard,
    fetchMyClasses,
    fetchMyHomework,
    fetchStudentHomework,
    invalidateCache,
    showLoading,
    hideLoading,
    setCurrentLanguageId,
    setCurrentLanguageName,
    setCurrentLanguageSlug,
    setShowAddLangModal,
    setRemoveLangModal,
    setShowUserPanel,
    setShowUserPanelState: setShowUserPanel,
    setNativeLanguage,
    setDefaultLanguageId,
    setUserLanguages,
    setCurrentUser,
    practiceGrammarId,
    setPracticeGrammarId,
    pendingConversationTopic,
    setPendingConversationTopic,
    mobileSidebarOpen,
    setMobileSidebarOpen,
    homeworkDraft,
    setHomeworkDraft,
    clearHomeworkDraft,
  };

  if (authChecking) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: "var(--surface)" }}
      >
        <div className="text-center">
          <div
            className="w-12 h-12 rounded-full border-4 border-t-transparent mx-auto mb-4 animate-spin"
            style={{
              borderColor: "var(--primary)",
              borderTopColor: "transparent",
            }}
          />
          <p className="text-sm" style={{ color: "var(--accent1)" }}>
            Loading...
          </p>
        </div>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <AppContext.Provider value={contextValue}>
        <LandingPage />
      </AppContext.Provider>
    );
  }

  // Determine which page to render
  function renderPage() {
    const { page, section } = route;
    // Teacher pages
    if (page === "teacher-classes") return <TeacherClassesPage />;
    if (page === "teacher-homework") return <TeacherHomeworkPage />;
    if (page === "create-homework") return <CreateHomeworkPage />;
    if (page === "homework-detail")
      return <CreateHomeworkPage homeworkId={route.homeworkId} editMode />;
    if (page === "student-homework") return <StudentHomeworkPage />;
    if (page === "student-homework-detail")
      return <StudentHomeworkDetailPage homeworkId={route.homeworkId} />;
    if (page === "dashboard") return <DashboardPage />;
    if (page === "language") {
      if (section === "notes") return <UploadPage />;
      if (section === "flashcards") return <FlashcardPage />;
      if (section === "practice") return <PracticePage />;
      if (section === "placement") return <PlacementPage />;
      if (section === "grammar-practice") return <GrammarPracticePage />;
      return <LanguagePage section={section || "vocabulary"} />;
    }
    // fallback
    return <DashboardPage />;
  }

  return (
    <AppContext.Provider value={contextValue}>
      <div className="min-h-screen" style={{ background: "var(--surface)" }}>
        {/* Mobile top bar */}
        <header className="lg:hidden fixed top-0 left-0 right-0 h-14 bg-[#f8faf9] border-b border-[rgba(172,179,178,0.2)] z-40 flex items-center px-4 gap-3">
          <button
            onClick={() => setMobileSidebarOpen(true)}
            className="p-2 rounded-lg"
            style={{ color: "var(--dark)" }}
            aria-label="Open menu"
          >
            <span
              className="material-symbols-outlined"
              style={{ fontSize: 24 }}
            >
              menu
            </span>
          </button>
          <h1
            className="text-xl font-bold tracking-tight"
            style={{ color: "var(--dark)" }}
          >
            Fluō
          </h1>
        </header>

        {/* Mobile sidebar backdrop */}
        {mobileSidebarOpen && (
          <div
            className="lg:hidden fixed inset-0 z-40"
            style={{
              background: "rgba(0,0,0,0.4)",
              backdropFilter: "blur(4px)",
            }}
            onClick={() => setMobileSidebarOpen(false)}
          />
        )}

        <Sidebar />
        <main className="lg:ml-72 min-h-screen px-4 py-6 pt-20 lg:px-12 lg:py-10 lg:pt-10">
          {renderPage()}
        </main>
        <LoadingOverlay />
        {showAddLangModal && <AddLanguageModal />}
        {removeLangModal.show && <RemoveLanguageModal />}
        {showUserPanel && <UserPanelModal />}
      </div>
    </AppContext.Provider>
  );
}
