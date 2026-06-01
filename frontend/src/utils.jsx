export function getLanguageEmoji(name) {
  const emojis = {
    Turkish: "🇹🇷",
    Spanish: "🇪🇸",
    French: "🇫🇷",
    Persian: "🦱",
    Korean: "🇰🇷",
    Japanese: "🇯🇵",
    German: "🇩🇪",
    English: "🇬🇧",
  };
  return emojis[name] || "🌍";
}

export function getLanguageSlug(name) {
  return name.toLowerCase();
}

export function getLanguageCode(name) {
  const codes = { Turkish: "TR", Spanish: "ES", French: "FR", Persian: "FA" };
  return codes[name] || name.substring(0, 2).toUpperCase();
}

export function LangFlag({ name, className = "", style = {} }) {
  if (name === "Persian") {
    return (
      <img
        src="/iran.png"
        alt="Persian"
        style={{
          width: "1.2em",
          height: "1.2em",
          objectFit: "contain",
          display: "inline-block",
          ...style,
        }}
        className={className}
      />
    );
  }
  return (
    <span className={className} style={style}>
      {getLanguageEmoji(name) || "🌍"}
    </span>
  );
}

export function speakText(text, rate = 0.85) {
  if (!text || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = rate;
  window.speechSynthesis.speak(utterance);
}

export function playAudio(hexAudio) {
  if (!hexAudio || hexAudio.length === 0) return;
  try {
    const bytes = new Uint8Array(
      hexAudio.match(/.{1,2}/g).map((byte) => parseInt(byte, 16)),
    );
    const blob = new Blob([bytes], { type: "audio/mpeg" });
    const audio = new Audio(URL.createObjectURL(blob));
    audio.play().catch(() => {
      const playOnClick = () => {
        audio.play().catch(() => {});
        document.removeEventListener("click", playOnClick);
      };
      document.addEventListener("click", playOnClick, { once: true });
    });
  } catch (err) {
    console.error("Audio processing error:", err);
  }
}

export function escapeAttr(str) {
  return (str || "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function escapeHtml(str) {
  return (str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function buildProficiencyDots(fluency) {
  const levels = { low: 1, medium: 2, high: 3 };
  const filled = levels[fluency] || 0;
  if (filled === 3) {
    return (
      <div className="flex items-center gap-2" style={{ color: "#56634f" }}>
        <span
          className="material-symbols-outlined"
          style={{ fontSize: 16, fontVariationSettings: "'FILL' 1" }}
        >
          verified
        </span>
        <span className="text-xs font-bold uppercase tracking-wider">
          Mastered
        </span>
      </div>
    );
  }
  const dots = [];
  for (let i = 0; i < 4; i++) {
    dots.push(
      <div
        key={i}
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background:
            i < filled ? "#56634f" : "var(--surface-container-highest)",
        }}
      />,
    );
  }
  return <div style={{ display: "flex", gap: 4 }}>{dots}</div>;
}

export function parsePath(path) {
  const parts = (path || "/").split("/").filter((p) => p);
  if (parts.length === 0) return { page: "dashboard" };
  if (parts[0] === "settings") return { page: "settings" };
  if (parts[0] === "teacher") {
    if (parts[1] === "classes") return { page: "teacher-classes" };
    if (parts[1] === "homework" && parts[2] === "create")
      return { page: "create-homework" };
    if (parts[1] === "homework" && parts[2] && parts[2] !== "create")
      return { page: "homework-detail", homeworkId: parseInt(parts[2]) };
    if (parts[1] === "homework") return { page: "teacher-homework" };
    return { page: "teacher-classes" };
  }
  if (parts[0] === "homework") {
    if (parts[1])
      return {
        page: "student-homework-detail",
        homeworkId: parseInt(parts[1]),
      };
    return { page: "student-homework" };
  }
  return {
    page: "language",
    langSlug: parts[0],
    section: parts[1] || "vocabulary",
  };
}
