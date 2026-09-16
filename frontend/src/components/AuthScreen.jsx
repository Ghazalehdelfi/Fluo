import { useState } from "react";
import { useApp } from "../context/AppContext";

export default function AuthScreen({ initialMode = "signin", onClose }) {
  const { doLogin, features } = useApp();
  const [mode, setMode] = useState(initialMode); // "signin" | "signup" | "forgot"
  const [step, setStep] = useState("form"); // signup: "form" | "verify"; forgot: "email" | "reset"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [role, setRole] = useState("student");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);

  function switchMode(next) {
    setMode(next);
    setStep("form");
    setError("");
    setInfo("");
    setCode("");
  }

  async function post(endpoint, payload) {
    const resp = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(typeof data.detail === "string" ? data.detail : "Request failed");
    }
    return data;
  }

  function loginWith(data) {
    doLogin(data.token, {
      email: data.email,
      credits: data.credits,
      role: data.role,
      enrolled_in_class: data.enrolled_in_class ?? false,
    });
  }

  async function handleSignin(e) {
    e?.preventDefault();
    setError("");
    if (!email.trim() || !password) {
      setError("Please fill in all fields");
      return;
    }
    setLoading(true);
    try {
      const data = await post("/api/auth/login", {
        email: email.trim(),
        password,
      });
      loginWith(data);
    } catch (err) {
      setError(err.message === "Request failed" ? "Login failed" : err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSignupDetails(e) {
    e?.preventDefault();
    setError("");
    if (!email.trim() || !password) {
      setError("Please fill in all fields");
      return;
    }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      setError("Please enter a valid email address");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      await post("/api/auth/register/request-code", { email: email.trim() });
      setStep("verify");
      setInfo(`We sent a 6-digit code to ${email.trim()}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSignupVerify(e) {
    e?.preventDefault();
    setError("");
    if (code.trim().length !== 6) {
      setError("Please enter the 6-digit code");
      return;
    }
    setLoading(true);
    try {
      const data = await post("/api/auth/register", {
        email: email.trim(),
        password,
        role,
        code: code.trim(),
      });
      loginWith(data);
    } catch (err) {
      setError(err.message === "Request failed" ? "Sign up failed" : err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleResendCode() {
    setError("");
    setInfo("");
    setLoading(true);
    try {
      const endpoint =
        mode === "forgot"
          ? "/api/auth/password-reset/request"
          : "/api/auth/register/request-code";
      await post(endpoint, { email: email.trim() });
      setInfo("A new code is on its way");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleForgotEmail(e) {
    e?.preventDefault();
    setError("");
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      setError("Please enter a valid email address");
      return;
    }
    setLoading(true);
    try {
      await post("/api/auth/password-reset/request", { email: email.trim() });
      setStep("reset");
      setInfo(`If an account exists for ${email.trim()}, a reset code is on its way`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleForgotReset(e) {
    e?.preventDefault();
    setError("");
    if (code.trim().length !== 6) {
      setError("Please enter the 6-digit code");
      return;
    }
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setError("Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      const data = await post("/api/auth/password-reset/confirm", {
        email: email.trim(),
        code: code.trim(),
        new_password: newPassword,
      });
      loginWith(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const subtitles = {
    signin: "Welcome back",
    signup: step === "verify" ? "Check your inbox" : "Create your account",
    forgot: step === "reset" ? "Choose a new password" : "Reset your password",
  };

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
        <p className="mt-1.5 text-sm text-[var(--accent1)]">{subtitles[mode]}</p>
      </div>

      {mode !== "forgot" && (
        <div className="mb-5 grid grid-cols-2 rounded-xl bg-[var(--surface-container-low)] p-1">
          <button
            type="button"
            onClick={() => switchMode("signin")}
            className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${mode === "signin" ? "bg-white text-[var(--dark)] shadow-sm" : "text-[var(--accent1)]"}`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => switchMode("signup")}
            className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${mode === "signup" ? "bg-white text-[var(--dark)] shadow-sm" : "text-[var(--accent1)]"}`}
          >
            Sign Up
          </button>
        </div>
      )}

      {/* ── Sign In ─────────────────────────────────────────── */}
      {mode === "signin" && (
        <form onSubmit={handleSignin} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--dark)]">
              Email
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
          <div className="text-right">
            <button
              type="button"
              onClick={() => switchMode("forgot")}
              className="text-xs font-semibold text-[var(--primary)] hover:underline"
            >
              Forgot your password?
            </button>
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full rounded-xl px-4 py-3 text-sm font-semibold disabled:opacity-60"
          >
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>
      )}

      {/* ── Sign Up: details ────────────────────────────────── */}
      {mode === "signup" && step === "form" && (
        <form onSubmit={handleSignupDetails} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--dark)]">
              Email
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
          {features?.teacher && (
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
          )}
          {error && <p className="text-xs text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full rounded-xl px-4 py-3 text-sm font-semibold disabled:opacity-60"
          >
            {loading ? "Sending code…" : "Continue"}
          </button>
        </form>
      )}

      {/* ── Sign Up: verify code ────────────────────────────── */}
      {mode === "signup" && step === "verify" && (
        <form onSubmit={handleSignupVerify} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--dark)]">
              Verification code
            </label>
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              className="input-field w-full rounded-xl px-4 py-2.5 text-center text-lg font-bold tracking-[0.5em]"
              placeholder="••••••"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            />
          </div>
          {info && <p className="text-xs text-[var(--accent1)]">{info}</p>}
          {error && <p className="text-xs text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full rounded-xl px-4 py-3 text-sm font-semibold disabled:opacity-60"
          >
            {loading ? "Creating account…" : "Verify & Create Account"}
          </button>
          <div className="flex items-center justify-between text-xs">
            <button
              type="button"
              onClick={() => {
                setStep("form");
                setCode("");
                setError("");
                setInfo("");
              }}
              className="font-semibold text-[var(--accent1)] hover:underline"
            >
              ← Back
            </button>
            <button
              type="button"
              onClick={handleResendCode}
              disabled={loading}
              className="font-semibold text-[var(--primary)] hover:underline disabled:opacity-60"
            >
              Resend code
            </button>
          </div>
        </form>
      )}

      {/* ── Forgot: enter email ─────────────────────────────── */}
      {mode === "forgot" && step === "form" && (
        <form onSubmit={handleForgotEmail} className="space-y-4">
          <p className="text-xs text-[var(--accent1)]">
            Enter the email you signed up with and we'll send you a code to
            reset your password.
          </p>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--dark)]">
              Email
            </label>
            <input
              type="text"
              className="input-field w-full rounded-xl px-4 py-2.5 text-sm"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full rounded-xl px-4 py-3 text-sm font-semibold disabled:opacity-60"
          >
            {loading ? "Sending code…" : "Send Reset Code"}
          </button>
          <div className="text-center">
            <button
              type="button"
              onClick={() => switchMode("signin")}
              className="text-xs font-semibold text-[var(--accent1)] hover:underline"
            >
              ← Back to sign in
            </button>
          </div>
        </form>
      )}

      {/* ── Forgot: reset password ──────────────────────────── */}
      {mode === "forgot" && step === "reset" && (
        <form onSubmit={handleForgotReset} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--dark)]">
              Reset code
            </label>
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              className="input-field w-full rounded-xl px-4 py-2.5 text-center text-lg font-bold tracking-[0.5em]"
              placeholder="••••••"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--dark)]">
              New password
            </label>
            <input
              type="password"
              className="input-field w-full rounded-xl px-4 py-2.5 text-sm"
              placeholder="••••••••"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--dark)]">
              Confirm new password
            </label>
            <input
              type="password"
              className="input-field w-full rounded-xl px-4 py-2.5 text-sm"
              placeholder="••••••••"
              value={confirmNewPassword}
              onChange={(e) => setConfirmNewPassword(e.target.value)}
            />
          </div>
          {info && <p className="text-xs text-[var(--accent1)]">{info}</p>}
          {error && <p className="text-xs text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full rounded-xl px-4 py-3 text-sm font-semibold disabled:opacity-60"
          >
            {loading ? "Resetting…" : "Reset Password & Sign In"}
          </button>
          <div className="flex items-center justify-between text-xs">
            <button
              type="button"
              onClick={() => switchMode("signin")}
              className="font-semibold text-[var(--accent1)] hover:underline"
            >
              ← Back to sign in
            </button>
            <button
              type="button"
              onClick={handleResendCode}
              disabled={loading}
              className="font-semibold text-[var(--primary)] hover:underline disabled:opacity-60"
            >
              Resend code
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
