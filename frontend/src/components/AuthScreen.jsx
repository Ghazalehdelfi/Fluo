import { useState } from "react";
import { useApp } from "../context/AppContext";

export default function AuthScreen({ initialMode = "signin", onClose }) {
  const { doLogin } = useApp();
  const [mode, setMode] = useState(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [role, setRole] = useState("student");
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
        body: JSON.stringify({
          email: email.trim(),
          password,
          ...(mode === "signup" && { role }),
        }),
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
    <div className="card relative w-full max-w-md rounded-3xl p-10 shadow-[0_24px_64px_rgba(17,56,44,0.18)]">
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
          <>
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
            <div>
              <label className="mb-2 block text-sm font-medium text-[var(--dark)]">
                I am a…
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setRole("student")}
                  className={`flex items-center gap-2 rounded-xl border px-4 py-3 text-sm font-semibold transition ${
                    role === "student"
                      ? "border-[var(--primary)] bg-[var(--primary-container)] text-[var(--dark)]"
                      : "border-[rgba(172,179,178,0.3)] bg-white text-[var(--accent1)] hover:bg-[var(--surface-container-low)]"
                  }`}
                >
                  <span
                    className="material-symbols-outlined"
                    style={{ fontSize: 18 }}
                  >
                    person
                  </span>
                  Self Learner
                </button>
                <button
                  type="button"
                  onClick={() => setRole("teacher")}
                  className={`flex items-center gap-2 rounded-xl border px-4 py-3 text-sm font-semibold transition ${
                    role === "teacher"
                      ? "border-[var(--primary)] bg-[var(--primary-container)] text-[var(--dark)]"
                      : "border-[rgba(172,179,178,0.3)] bg-white text-[var(--accent1)] hover:bg-[var(--surface-container-low)]"
                  }`}
                >
                  <span
                    className="material-symbols-outlined"
                    style={{ fontSize: 18 }}
                  >
                    school
                  </span>
                  Teacher
                </button>
              </div>
            </div>
          </>
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
