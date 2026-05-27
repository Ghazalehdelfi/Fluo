import { useState } from "react";
import { useApp } from "../context/AppContext";

export default function AuthScreen() {
  const { doLogin } = useApp();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e) {
    e?.preventDefault();
    setError("");
    if (!email.trim() || !password) {
      setError("Please fill in all fields");
      return;
    }
    setLoading(true);
    try {
      const resp = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setError(data.detail || "Login failed");
        return;
      }
      doLogin(data.token, { email: data.email, credits: data.credits, role: data.role });
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f8faf9]">
      <div className="card rounded-3xl p-10 max-w-sm w-full mx-4 shadow-[0_8px_32px_rgba(45,52,51,0.08)]">
        <div className="text-center mb-8">
          <h1
            className="text-3xl font-bold tracking-tight"
            style={{ color: "var(--dark)" }}
          >
            Fluō
          </h1>
        </div>
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label
              className="block text-sm font-medium mb-1"
              style={{ color: "var(--dark)" }}
            >
              Username
            </label>
            <input
              type="text"
              className="input-field w-full px-4 py-2.5 rounded-xl text-sm"
              placeholder="Your username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label
              className="block text-sm font-medium mb-1"
              style={{ color: "var(--dark)" }}
            >
              Password
            </label>
            <input
              type="password"
              className="input-field w-full px-4 py-2.5 rounded-xl text-sm"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && <div className="text-red-500 text-xs">{error}</div>}
          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full px-4 py-3 rounded-xl text-sm font-medium disabled:opacity-60"
          >
            {loading ? "Logging in…" : "Log In"}
          </button>
        </form>
      </div>
    </div>
  );
}
