import { useState } from "react";
import { useApp } from "../context/AppContext";

export default function AuthScreen({ initialMode = "signin", onClose }) {
  const { doLogin } = useApp();
  const [mode, setMode] = useState(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleAuth(e) {
    e?.preventDefault();
    setError("");
    if (!email.trim() || !password) {
      setError("Please fill in all fields");
      return;
    }
    if (mode === "signup") {
      if (password.length < 8) {
        setError("Password must be at least 8 characters");
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match");
        return;
      }
    }
    setLoading(true);
    try {
      const endpoint =
        mode === "signup" ? "/api/auth/register" : "/api/auth/login";
      const resp = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setError(
          data.detail ||
            (mode === "signup" ? "Sign up failed" : "Login failed"),
        );
        return;
      }
      doLogin(data.token, {
        email: data.email,
        credits: data.credits,
        role: data.role,
      });
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card relative w-full max-w-sm rounded-3xl p-8 shadow-[0_24px_64px_rgba(17,56,44,0.18)]">
      <section className="promo-panel rounded-3xl p-8 md:p-10 lg:p-12">
        <div className="inline-flex items-center rounded-full border border-[rgba(17,56,44,0.16)] bg-white/75 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--primary)]">
          Language coaching, reimagined
        </div>

        <h1 className="mt-5 text-4xl font-black leading-tight tracking-tight text-[var(--dark)] md:text-5xl">
          Fluō helps students think in a new language, not just memorize words.
        </h1>

        <p className="mt-5 max-w-2xl text-base leading-relaxed text-[var(--accent1)] md:text-lg">
          Upload notes, build personalized flashcards, and practice in adaptive
          conversations that respond to your level. Teachers can assign focused
          homework and track real progress.
        </p>

        <div className="mt-8 grid gap-3 sm:grid-cols-2">
          <div className="feature-tile rounded-2xl p-4">
            <h3 className="text-sm font-extrabold uppercase tracking-[0.14em] text-[var(--dark)]">
              Adaptive Practice
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--accent1)]">
              Dialogue sessions adjust to vocabulary, grammar confidence, and
              CEFR level.
            </p>
          </div>
          <div className="feature-tile rounded-2xl p-4">
            <h3 className="text-sm font-extrabold uppercase tracking-[0.14em] text-[var(--dark)]">
              Teacher Workflows
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--accent1)]">
              Create classes, attach vocabulary and grammar tasks, then review
              student submissions.
            </p>
          </div>
          <div className="feature-tile rounded-2xl p-4">
            <h3 className="text-sm font-extrabold uppercase tracking-[0.14em] text-[var(--dark)]">
              Smart Note Extraction
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--accent1)]">
              Turn lecture notes and study sheets into instantly usable learning
              material.
            </p>
          </div>
          <div className="feature-tile rounded-2xl p-4">
            <h3 className="text-sm font-extrabold uppercase tracking-[0.14em] text-[var(--dark)]">
              Progress Visibility
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--accent1)]">
              Track fluency growth, practice consistency, and topic mastery in
              one dashboard.
            </p>
          </div>
        </div>

        <div className="mt-8 grid gap-3 md:grid-cols-3">
          <div className="pricing-tile rounded-2xl p-4">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent1)]">
              Starter
            </p>
            <p className="mt-2 text-2xl font-black text-[var(--dark)]">Free</p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--accent1)]">
              Perfect for getting started with note uploads and daily speaking
              drills.
            </p>
          </div>
          <div className="pricing-tile pricing-tile-highlight rounded-2xl p-4">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--dark)]">
              Pro Learner
            </p>
            <p className="mt-2 text-2xl font-black text-[var(--dark)]">
              Most Popular
            </p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--dark)]">
              Deeper conversation sessions, faster growth loops, and richer
              progress analytics.
            </p>
          </div>
          <div className="pricing-tile rounded-2xl p-4">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--accent1)]">
              Teacher Suite
            </p>
            <p className="mt-2 text-2xl font-black text-[var(--dark)]">
              Classroom
            </p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--accent1)]">
              Build homework, manage classes, and track student learning
              outcomes in one view.
            </p>
          </div>
        </div>

        <div className="mt-8 grid gap-3 sm:grid-cols-2">
          <blockquote className="testimonial-tile rounded-2xl p-4">
            <p className="text-sm leading-relaxed text-[var(--dark)]">
              "My students finally practice between classes. Homework completion
              has never been this consistent."
            </p>
            <footer className="mt-3 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--accent1)]">
              Instructor, B1 Turkish Cohort
            </footer>
          </blockquote>
          <blockquote className="testimonial-tile rounded-2xl p-4">
            <p className="text-sm leading-relaxed text-[var(--dark)]">
              "The conversation practice feels like a coach who actually
              remembers what I struggle with."
            </p>
            <footer className="mt-3 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--accent1)]">
              Student, Independent Learner
            </footer>
          </blockquote>
        </div>

        <div className="mt-8 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => setMode("signup")}
            className="btn-primary rounded-xl px-5 py-3 text-sm font-semibold"
          >
            Create Account
          </button>
          <button
            type="button"
            onClick={() => setMode("signin")}
            className="btn-secondary rounded-xl px-5 py-3 text-sm font-semibold"
          >
            Sign In
          </button>
        </div>
      </section>

      {onClose && (
        <button
          onClick={onClose}
          className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-full text-[var(--accent1)] transition hover:bg-[var(--surface-container-high)]"
          aria-label="Close"
        >
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>
            close
          </span>
        </button>
      )}

      <div className="mb-7 text-center">
        <h2 className="text-2xl font-black tracking-tight text-[var(--dark)]">
          Fluō
        </h2>
        <p className="mt-1.5 text-sm text-[var(--accent1)]">
          {mode === "signup" ? "Create your account" : "Welcome back"}
        </p>
      </div>

      <div className="mb-5 grid grid-cols-2 rounded-xl bg-[var(--surface-container-low)] p-1">
        <button
          type="button"
          onClick={() => {
            setMode("signin");
            setError("");
          }}
          className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${mode === "signin" ? "bg-white text-[var(--dark)] shadow-sm" : "text-[var(--accent1)]"}`}
        >
          Sign In
        </button>
        <button
          type="button"
          onClick={() => {
            setMode("signup");
            setError("");
          }}
          className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${mode === "signup" ? "bg-white text-[var(--dark)] shadow-sm" : "text-[var(--accent1)]"}`}
        >
          Sign Up
        </button>
      </div>

      <form onSubmit={handleAuth} className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--dark)]">
            Email or Username
          </label>
          <input
            type="text"
            className="input-field w-full rounded-xl px-4 py-2.5 text-sm"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--dark)]">
            Password
          </label>
          <input
            type="password"
            className="input-field w-full rounded-xl px-4 py-2.5 text-sm"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {mode === "signup" && (
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--dark)]">
              Confirm Password
            </label>
            <input
              type="password"
              className="input-field w-full rounded-xl px-4 py-2.5 text-sm"
              placeholder="••••••••"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </div>
        )}
        {error && <p className="text-xs text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="btn-primary w-full rounded-xl px-4 py-3 text-sm font-semibold disabled:opacity-60"
        >
          {loading
            ? mode === "signup"
              ? "Creating account…"
              : "Signing in…"
            : mode === "signup"
              ? "Create Account"
              : "Sign In"}
        </button>
      </form>
    </div>
  );
}
