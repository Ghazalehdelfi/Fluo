import { useState, useEffect, useRef } from "react";
import { useApp } from "../context/AppContext";
import { getLanguageEmoji, getLanguageSlug } from "../utils.jsx";

function LanguageSwitcher() {
  const {
    userLanguages,
    availableLanguages,
    currentLanguageId,
    currentLanguageName,
    navigate,
    setCurrentLanguageId,
    setCurrentLanguageName,
    setCurrentLanguageSlug,
    setDefaultLanguageId,
    apiFetch,
    setRemoveLangModal,
    loadLanguages,
  } = useApp();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function onClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  async function switchLanguage(lang) {
    setOpen(false);
    setCurrentLanguageId(lang.id);
    setCurrentLanguageName(lang.name);
    setCurrentLanguageSlug(getLanguageSlug(lang.name));
    try {
      await apiFetch("/api/settings/default-language", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language_id: lang.id }),
      });
      setDefaultLanguageId(lang.id);
    } catch {}
    navigate("/");
  }

  const label = currentLanguageName || "Select Language";
  const emoji = currentLanguageName
    ? getLanguageEmoji(currentLanguageName)
    : "🌍";

  return (
    <div className="lang-switcher" ref={ref}>
      <button className="lang-switcher-btn" onClick={() => setOpen((o) => !o)}>
        <span className="text-lg">{emoji}</span>
        <span className="flex-1 text-left truncate">{label}</span>
        <svg
          className="w-4 h-4 shrink-0 transition-transform"
          style={{ transform: open ? "rotate(180deg)" : "" }}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>
      <div className={`lang-switcher-dropdown ${open ? "open" : ""}`}>
        {userLanguages.length === 0 ? (
          <div
            className="lang-switcher-option"
            style={{ color: "var(--primary)" }}
            onClick={() => {
              setOpen(false); /* handled by Add Lang btn */
            }}
          >
            <span
              className="material-symbols-outlined"
              style={{ fontSize: 18 }}
            >
              translate
            </span>
            <span>No languages yet</span>
          </div>
        ) : (
          userLanguages.map((lang) => (
            <div
              key={lang.id}
              className={`lang-switcher-option ${lang.id === currentLanguageId ? "active" : ""}`}
              style={{ justifyContent: "space-between" }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  flex: 1,
                }}
                onClick={() => switchLanguage(lang)}
              >
                <span className="text-lg">{getLanguageEmoji(lang.name)}</span>
                <span>{lang.name}</span>
              </div>
              <span
                className="material-symbols-outlined"
                style={{
                  fontSize: 16,
                  color: "var(--accent1)",
                  cursor: "pointer",
                  padding: 2,
                  borderRadius: 4,
                  transition: "color 0.15s",
                }}
                onMouseOver={(e) => (e.currentTarget.style.color = "#ef4444")}
                onMouseOut={(e) =>
                  (e.currentTarget.style.color = "var(--accent1)")
                }
                onClick={(e) => {
                  e.stopPropagation();
                  setOpen(false);
                  setRemoveLangModal({
                    show: true,
                    id: lang.id,
                    name: lang.name,
                  });
                }}
              >
                close
              </span>
            </div>
          ))
        )}
        {availableLanguages.length > 0 && (
          <div
            className="lang-switcher-option"
            style={{
              borderTop: "1px solid rgba(172,179,178,0.2)",
              marginTop: 4,
              paddingTop: 10,
              color: "var(--primary)",
            }}
            onClick={() => {
              setOpen(false);
              useApp;
            }}
          >
            {/* handled via AddLangBtn in Sidebar */}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Sidebar() {
  const {
    currentUser,
    route,
    navigate,
    navigateToActiveSection,
    currentLanguageSlug,
    setShowAddLangModal,
    setShowUserPanelState,
    doLogout,
    mobileSidebarOpen,
    setMobileSidebarOpen,
  } = useApp();

  const page = route.page;
  const section = route.section;
  const isTeacher = currentUser?.role === "teacher";

  function closeMobile() {
    setMobileSidebarOpen(false);
  }

  function activeClass(id) {
    if (id === "dashboard" && page === "dashboard") return "active";
    if (id === "teacher-classes" && page === "teacher-classes") return "active";
    if (
      id === "teacher-homework" &&
      (page === "teacher-homework" ||
        page === "create-homework" ||
        page === "homework-detail")
    )
      return "active";
    if (
      id === "student-homework" &&
      (page === "student-homework" || page === "student-homework-detail")
    )
      return "active";
    if (id === "notes" && page === "language" && section === "notes")
      return "active";
    if (
      id === "vocabulary" &&
      page === "language" &&
      (section === "vocabulary" || section === "grammar")
    )
      return "active";
    if (id === "flashcards" && page === "language" && section === "flashcards")
      return "active";
    if (id === "practice" && page === "language" && section === "practice")
      return "active";
    if (
      id === "grammar-practice" &&
      page === "language" &&
      section === "grammar-practice"
    )
      return "active";
    return "";
  }

  const userInitial = (currentUser?.email || "?")[0].toUpperCase();
  const credits = (currentUser?.credits || 0).toFixed(2);

  return (
    <aside
      className={`sidebar-drawer fixed left-0 top-0 h-screen w-72 flex flex-col py-8 bg-[#f8faf9] z-50 transition-transform duration-300 lg:translate-x-0 ${mobileSidebarOpen ? "translate-x-0" : "-translate-x-full"}`}
    >
      <div className="px-8 mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-[#2d3433]">
          Fluō
        </h1>
        {/* Close button - mobile only */}
        <button
          className="lg:hidden p-1 rounded-lg"
          style={{ color: "var(--accent1)" }}
          onClick={closeMobile}
          aria-label="Close menu"
        >
          <span className="material-symbols-outlined" style={{ fontSize: 22 }}>
            close
          </span>
        </button>
      </div>

      {!isTeacher && (
        <div className="px-6 mb-6">
          <LanguageSwitcherWithAdd />
        </div>
      )}

      <nav className="flex-1 px-4 space-y-1">
        {isTeacher ? (
          // Teacher navigation
          <>
            <a
              className={`sidebar-nav-item ${activeClass("teacher-classes")}`}
              onClick={() => {
                navigate("/teacher/classes");
                closeMobile();
              }}
            >
              <span className="material-symbols-outlined">groups</span>
              <span>My Classes</span>
            </a>
            <a
              className={`sidebar-nav-item ${activeClass("teacher-homework")}`}
              onClick={() => {
                navigate("/teacher/homework");
                closeMobile();
              }}
            >
              <span className="material-symbols-outlined">assignment</span>
              <span>Homework</span>
            </a>
            <div className="px-3 pt-4 pb-1">
              <p
                className="text-[10px] uppercase tracking-widest font-semibold"
                style={{ color: "var(--accent1)" }}
              >
                My Content
              </p>
            </div>
            <a
              className={`sidebar-nav-item ${activeClass("notes")}`}
              onClick={() => {
                navigateToActiveSection("notes");
                closeMobile();
              }}
            >
              <span className="material-symbols-outlined">upload_file</span>
              <span>Upload Notes</span>
            </a>
            <a
              className={`sidebar-nav-item ${activeClass("vocabulary")}`}
              onClick={() => {
                navigateToActiveSection("vocabulary");
                closeMobile();
              }}
            >
              <span className="material-symbols-outlined">menu_book</span>
              <span>Knowledge Base</span>
            </a>
          </>
        ) : (
          // Student navigation
          <>
            <a
              className={`sidebar-nav-item ${activeClass("dashboard")}`}
              onClick={() => {
                navigate("/");
                closeMobile();
              }}
            >
              <span className="material-symbols-outlined">dashboard</span>
              <span>Dashboard</span>
            </a>
            <a
              className={`sidebar-nav-item ${activeClass("student-homework")}`}
              onClick={() => {
                navigate("/homework");
                closeMobile();
              }}
            >
              <span className="material-symbols-outlined">assignment</span>
              <span>My Homework</span>
            </a>
            <a
              className={`sidebar-nav-item ${activeClass("notes")}`}
              onClick={() => {
                navigateToActiveSection("notes");
                closeMobile();
              }}
            >
              <span className="material-symbols-outlined">upload_file</span>
              <span>Upload Notes</span>
            </a>
            <a
              className={`sidebar-nav-item ${activeClass("vocabulary")}`}
              onClick={() => {
                navigateToActiveSection("vocabulary");
                closeMobile();
              }}
            >
              <span className="material-symbols-outlined">menu_book</span>
              <span>Knowledge Base</span>
            </a>
            <a
              className={`sidebar-nav-item ${activeClass("flashcards")}`}
              onClick={() => {
                navigateToActiveSection("flashcards");
                closeMobile();
              }}
            >
              <span className="material-symbols-outlined">quiz</span>
              <span>Flashcards</span>
            </a>
            <a
              className={`sidebar-nav-item ${activeClass("practice")}`}
              onClick={() => {
                navigateToActiveSection("practice");
                closeMobile();
              }}
            >
              <span className="material-symbols-outlined">fitness_center</span>
              <span>Conversation Practice</span>
            </a>
            <a
              className={`sidebar-nav-item ${activeClass("grammar-practice")}`}
              onClick={() => {
                navigateToActiveSection("grammar-practice");
                closeMobile();
              }}
            >
              <span className="material-symbols-outlined">exercise</span>
              <span>Grammar Practice</span>
            </a>
          </>
        )}
      </nav>

      <div className="px-4 mt-auto space-y-1">
        <div
          className="px-6 py-4 mt-4 bg-[#eaefee] rounded-2xl flex items-center gap-3 mx-2 cursor-pointer hover:bg-[#dde5e3] transition-colors"
          onClick={() => {
            setShowUserPanelState(true);
            closeMobile();
          }}
        >
          <div className="w-8 h-8 rounded-full bg-[#436565] flex items-center justify-center text-xs font-bold text-white">
            {userInitial}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-bold text-[#2d3433] truncate">
              {currentUser?.email || "Account"}
            </p>
            {isTeacher ? (
              <p className="text-[10px] text-[#596060] uppercase tracking-wider">
                Teacher
              </p>
            ) : (
              <p className="text-[10px] text-[#596060] uppercase tracking-wider">
                {credits} credits
              </p>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}

// Wrapped version that includes the Add Language button
function LanguageSwitcherWithAdd() {
  const { availableLanguages, setShowAddLangModal } = useApp();
  const [open, setOpen] = useState(false);
  const {
    userLanguages,
    currentLanguageId,
    currentLanguageName,
    navigate,
    setCurrentLanguageId,
    setCurrentLanguageName,
    setCurrentLanguageSlug,
    setDefaultLanguageId,
    apiFetch,
    setRemoveLangModal,
  } = useApp();
  const ref = useRef(null);

  useEffect(() => {
    function onClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  async function switchLanguage(lang) {
    setOpen(false);
    setCurrentLanguageId(lang.id);
    setCurrentLanguageName(lang.name);
    setCurrentLanguageSlug(getLanguageSlug(lang.name));
    try {
      await apiFetch("/api/settings/default-language", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language_id: lang.id }),
      });
      setDefaultLanguageId(lang.id);
    } catch {}
    navigate("/");
  }

  const label = currentLanguageName || "Select Language";
  const emoji = currentLanguageName
    ? getLanguageEmoji(currentLanguageName)
    : "🌍";

  return (
    <div className="lang-switcher" ref={ref}>
      <button className="lang-switcher-btn" onClick={() => setOpen((o) => !o)}>
        <span className="text-lg">{emoji}</span>
        <span className="flex-1 text-left truncate">{label}</span>
        <svg
          className="w-4 h-4 shrink-0 transition-transform"
          style={{ transform: open ? "rotate(180deg)" : "" }}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>
      <div className={`lang-switcher-dropdown ${open ? "open" : ""}`}>
        {userLanguages.length === 0 && (
          <div
            className="lang-switcher-option"
            style={{ color: "var(--accent1)" }}
          >
            <span>No languages yet</span>
          </div>
        )}
        {userLanguages.map((lang) => (
          <div
            key={lang.id}
            className={`lang-switcher-option ${lang.id === currentLanguageId ? "active" : ""}`}
            style={{ justifyContent: "space-between" }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                flex: 1,
              }}
              onClick={() => switchLanguage(lang)}
            >
              <span className="text-lg">{getLanguageEmoji(lang.name)}</span>
              <span>{lang.name}</span>
            </div>
            <span
              className="material-symbols-outlined"
              style={{
                fontSize: 16,
                color: "var(--accent1)",
                cursor: "pointer",
                padding: 2,
                borderRadius: 4,
                transition: "color 0.15s",
              }}
              onMouseOver={(e) => (e.currentTarget.style.color = "#ef4444")}
              onMouseOut={(e) =>
                (e.currentTarget.style.color = "var(--accent1)")
              }
              onClick={(e) => {
                e.stopPropagation();
                setOpen(false);
                setRemoveLangModal({
                  show: true,
                  id: lang.id,
                  name: lang.name,
                });
              }}
            >
              close
            </span>
          </div>
        ))}
        {availableLanguages.length > 0 && (
          <div
            className="lang-switcher-option"
            style={{
              borderTop: "1px solid rgba(172,179,178,0.2)",
              marginTop: 4,
              paddingTop: 10,
              color: "var(--primary)",
            }}
            onClick={() => {
              setOpen(false);
              setShowAddLangModal(true);
            }}
          >
            <span
              className="material-symbols-outlined"
              style={{ fontSize: 18 }}
            >
              add
            </span>
            <span>Add Language</span>
          </div>
        )}
      </div>
    </div>
  );
}
