import { useState } from "react";
import AuthScreen from "../components/AuthScreen.jsx";

const LEARNER_FEATURES = [
  {
    icon: "upload_file",
    title: "Upload Your Notes",
    body: "Snap a photo of your notebook, paste text, or upload a PDF. Fluō extracts vocabulary and grammar automatically — turning your study material into learning cards in seconds.",
  },
  {
    icon: "auto_stories",
    title: "Your Personal Knowledge Base",
    body: "Every word and grammar rule you've ever added lives in one searchable place. It grows with you, stays organised, so nothing you've learned gets lost.",
  },
  {
    icon: "style",
    title: "Smart Flashcard Drills",
    body: "Review sessions focus on what you're weakest on. Fluency scores update as you practice, so cards get harder or easier based on real performance — not a fixed schedule.",
  },
  {
    icon: "record_voice_over",
    title: "Live Conversation Practice",
    body: "Start an AI-powered dialogue that pulls vocab and grammar straight from your knowledge base. Practice exactly what you've been studying — not random beginner phrases.",
  },
  {
    icon: "spellcheck",
    title: "Grammar Coaching",
    body: "Get targeted drills for grammar concepts you've actually encountered. The AI breaks them down, gives examples, and corrects you in context — not out of a textbook.",
  },
  {
    icon: "trending_up",
    title: "Track Your Progress",
    body: "Watch fluency scores rise across vocab and grammar. See which words have moved from 'learning' to 'confident', and which topics still need work.",
  },
];

const TEACHER_FEATURES = [
  {
    icon: "groups",
    title: "Manage Your Classes",
    body: "Create student groups for each language or cohort. Students join with a code and immediately have access to assigned material.",
  },
  {
    icon: "assignment",
    title: "Assign Targeted Homework",
    body: "Attach specific vocabulary lists and grammar rules directly to homework tasks. Students practise exactly what you've taught in class.",
  },
  {
    icon: "insights",
    title: "Track Student Progress",
    body: "See fluency scores, homework completion, and practice frequency for each student — without chasing anyone down for updates.",
  },
];

export default function LandingPage() {
  const [showAuth, setShowAuth] = useState(false);
  const [authMode, setAuthMode] = useState("signup");

  function openAuth(mode = "signup") {
    setAuthMode(mode);
    setShowAuth(true);
  }

  return (
    <div className="min-h-screen bg-[var(--light)]">
      {/* ── Navbar ─────────────────────────────────── */}
      <header className="sticky top-0 z-40 border-b border-[rgba(172,179,178,0.18)] bg-[rgba(248,250,249,0.9)] backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3 md:px-10">
          <span className="text-xl font-black tracking-tight text-[var(--dark)]">
            Fluō
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => openAuth("signin")}
              className="btn-secondary rounded-xl px-4 py-2 text-sm font-semibold"
            >
              Sign In
            </button>
            <button
              onClick={() => openAuth("signup")}
              className="btn-primary rounded-xl px-4 py-2 text-sm font-semibold"
            >
              Get Started
            </button>
          </div>
        </div>
      </header>

      {/* ── Hero ───────────────────────────────────── */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute -top-32 -left-32 h-80 w-80 rounded-full bg-[rgba(114,168,151,0.25)] blur-[72px]" />
        <div className="pointer-events-none absolute -bottom-20 right-0 h-72 w-72 rounded-full bg-[rgba(241,204,131,0.28)] blur-[64px]" />
        <div className="relative mx-auto max-w-4xl px-5 py-24 text-center md:px-10 md:py-32">
          <div className="inline-flex items-center rounded-full border border-[rgba(67,101,101,0.22)] bg-white px-4 py-1.5 text-xs font-bold uppercase tracking-widest text-[var(--primary)]">
            Your personal language learning companion
          </div>
          <h1 className="mt-6 text-5xl font-black leading-[1.08] tracking-tight text-[var(--dark)] md:text-6xl lg:text-[4.5rem]">
            Optimize your
            <br />
            <span className="text-[var(--primary)]">notes and practices.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-[var(--accent1)] md:text-xl">
            Fluō turns your notes, textbooks, and study sheets into flashcards,
            grammar drills, and live AI conversation practice — all built around
            what <em>you're</em> actually studying.
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <button
              onClick={() => openAuth("signup")}
              className="btn-primary rounded-2xl px-7 py-3.5 text-base font-semibold"
            >
              Start for free
            </button>
            <button
              onClick={() => openAuth("signin")}
              className="btn-secondary rounded-2xl px-7 py-3.5 text-base font-semibold"
            >
              Sign in
            </button>
          </div>

          {/* Trust bar */}
          <div className="mt-8 flex flex-wrap items-center justify-center gap-4 text-xs font-semibold text-[var(--accent1)]">
            <span className="flex items-center gap-1.5">
              <span
                className="material-symbols-outlined text-[var(--primary)]"
                style={{ fontSize: 16 }}
              >
                check_circle
              </span>
              No subscription
            </span>
            <span className="text-[var(--outline-variant)]">·</span>
            <span className="flex items-center gap-1.5">
              <span
                className="material-symbols-outlined text-[var(--primary)]"
                style={{ fontSize: 16 }}
              >
                bolt
              </span>
              Pay only for what you use
            </span>
            <span className="text-[var(--outline-variant)]">·</span>
            <span className="flex items-center gap-1.5">
              <span
                className="material-symbols-outlined text-[var(--primary)]"
                style={{ fontSize: 16 }}
              >
                redeem
              </span>
              100 free credits on sign-up
            </span>
          </div>
        </div>
      </section>

      {/* ── Self Learner Section ────────────────────── */}
      <section
        id="self-learner"
        className="mt-16 bg-[var(--surface-container-low)] py-16"
      >
        <div className="mx-auto max-w-6xl px-5 md:px-10">
          <h2 className="mt-2 max-w-2xl text-3xl font-black leading-tight tracking-tight text-[var(--dark)] md:text-4xl">
            Who is Fluō for?
          </h2>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--accent1)]">
            Fluō is designed for anyone with an existing learning practice. If
            you already have notes, textbooks, or worksheets, Fluō can turn them
            into a personalized learning companion that helps you retain more
            and practice more effectively.
          </p>

          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {LEARNER_FEATURES.map((f) => (
              <div
                key={f.title}
                className="rounded-2xl border border-[rgba(67,101,101,0.12)] bg-white p-5 transition-all hover:-translate-y-0.5 hover:shadow-[0_8px_24px_rgba(17,56,44,0.08)]"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--primary-container)]">
                  <span
                    className="material-symbols-outlined text-[var(--primary)]"
                    style={{ fontSize: 22 }}
                  >
                    {f.icon}
                  </span>
                </div>
                <h3 className="mt-4 text-sm font-black text-[var(--dark)]">
                  {f.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--accent1)]">
                  {f.body}
                </p>
              </div>
            ))}
          </div>

          <div className="mt-10">
            <button
              onClick={() => openAuth("signup")}
              className="btn-primary rounded-2xl px-7 py-3.5 text-sm font-semibold"
            >
              Start learning for free
            </button>
          </div>
        </div>
      </section>

      {/* ── Testimonials ───────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 py-16 md:px-10">
        <h2 className="text-center text-2xl font-black tracking-tight text-[var(--dark)]">
          What learners are saying
        </h2>
        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <blockquote className="testimonial-tile rounded-2xl p-5">
            <p className="text-sm leading-relaxed text-[var(--dark)]">
              "I uploaded my Turkish class notes and was doing real conversation
              practice the same afternoon. No app has ever worked that way
              before."
            </p>
            <footer className="mt-4 text-xs font-bold uppercase tracking-wider text-[var(--accent1)]">
              — Yuki, learning Turkish
            </footer>
          </blockquote>
          <blockquote className="testimonial-tile rounded-2xl p-5">
            <p className="text-sm leading-relaxed text-[var(--dark)]">
              "Finally a tool that works from <em>my</em> material. I
              photographed my grammar worksheets and Fluō built drills from them
              automatically."
            </p>
            <footer className="mt-4 text-xs font-bold uppercase tracking-wider text-[var(--accent1)]">
              — Céline, learning Spanish
            </footer>
          </blockquote>
          <blockquote className="testimonial-tile rounded-2xl p-5">
            <p className="text-sm leading-relaxed text-[var(--dark)]">
              "The AI conversation feels like a patient tutor who already knows
              what I've studied. I can actually practice on the bus now."
            </p>
            <footer className="mt-4 text-xs font-bold uppercase tracking-wider text-[var(--accent1)]">
              — Mariam, learning French
            </footer>
          </blockquote>
        </div>
      </section>

      {/* ── Pricing model ──────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 py-16 md:px-10">
        <div className="rounded-3xl border border-[rgba(67,101,101,0.18)] bg-white p-8 md:p-12">
          <div className="grid gap-10 md:grid-cols-2 md:items-center">
            <div>
              <div className="mb-4 inline-flex items-center rounded-full bg-[var(--primary-container)] px-4 py-1.5">
                <span className="text-xs font-bold uppercase tracking-widest text-[var(--primary)]">
                  Pricing
                </span>
              </div>
              <h2 className="text-3xl font-black leading-tight tracking-tight text-[var(--dark)] md:text-4xl">
                No subscription.
                <br />
                Ever.
              </h2>
              <p className="mt-4 text-base leading-relaxed text-[var(--accent1)]">
                Fluō runs on a simple credit system. You top up when you want,
                spend only when you use AI features, and never get charged for
                sitting idle. No monthly fees, no lock-in.
              </p>
              <div className="mt-5 inline-flex items-center gap-2.5 rounded-2xl border border-[rgba(67,101,101,0.25)] bg-[var(--primary-container)] px-5 py-3">
                <span
                  className="material-symbols-outlined text-[var(--primary)]"
                  style={{ fontSize: 22 }}
                >
                  redeem
                </span>
                <span className="text-sm font-bold text-[var(--dark)]">
                  Sign up today and get{" "}
                  <span className="text-[var(--primary)]">
                    100 free credits
                  </span>{" "}
                  — no card required.
                </span>
              </div>
              <button
                onClick={() => openAuth("signup")}
                className="btn-primary mt-6 rounded-2xl px-6 py-3 text-sm font-semibold"
              >
                Get free starter credits
              </button>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl bg-[var(--surface-container-low)] p-5">
                <span
                  className="material-symbols-outlined text-[var(--primary)]"
                  style={{ fontSize: 28 }}
                >
                  account_balance_wallet
                </span>
                <h3 className="mt-3 text-sm font-black text-[var(--dark)]">
                  Top up any time
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-[var(--accent1)]">
                  Add credits whenever you need them — $5, $10, or more. They
                  never expire.
                </p>
              </div>
              <div className="rounded-2xl bg-[var(--surface-container-low)] p-5">
                <span
                  className="material-symbols-outlined text-[var(--primary)]"
                  style={{ fontSize: 28 }}
                >
                  savings
                </span>
                <h3 className="mt-3 text-sm font-black text-[var(--dark)]">
                  Pay per session
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-[var(--accent1)]">
                  Credits are deducted only when you run AI conversations, note
                  extraction, or TTS. Browse and review for free.
                </p>
              </div>
              <div className="rounded-2xl bg-[var(--surface-container-low)] p-5">
                <span
                  className="material-symbols-outlined text-[var(--primary)]"
                  style={{ fontSize: 28 }}
                >
                  redeem
                </span>
                <h3 className="mt-3 text-sm font-black text-[var(--dark)]">
                  100 credits free to start
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-[var(--accent1)]">
                  Every new account gets 100 free starter credits — enough to
                  explore flashcards, live conversation practice, and note
                  uploads.
                </p>
              </div>
              <div className="rounded-2xl bg-[var(--surface-container-low)] p-5">
                <span
                  className="material-symbols-outlined text-[var(--primary)]"
                  style={{ fontSize: 28 }}
                >
                  no_encryption
                </span>
                <h3 className="mt-3 text-sm font-black text-[var(--dark)]">
                  No lock-in
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-[var(--accent1)]">
                  Cancel nothing. There's nothing to cancel. Use Fluō as much or
                  as little as suits your schedule.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Contact ────────────────────────────────── */}
      <section className="border-t border-[rgba(172,179,178,0.2)] px-5 py-14 md:px-10">
        <div className="mx-auto max-w-xl text-center">
          <h2 className="text-2xl font-black tracking-tight text-[var(--dark)]">
            Get in touch
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-[var(--accent1)]">
            Questions, feedback, or just want to say hello? We'd love to hear
            from you.
          </p>
          <a
            href="mailto:fluolearn@gmail.com"
            className="btn-primary mt-6 inline-flex items-center gap-2 rounded-2xl px-7 py-3.5 text-sm font-semibold"
          >
            <span
              className="material-symbols-outlined"
              style={{ fontSize: 18 }}
            >
              mail
            </span>
            fluolearn@gmail.com
          </a>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────── */}
      <footer className="border-t border-[rgba(172,179,178,0.2)] px-5 py-8 text-center text-xs text-[var(--accent1)] md:px-10">
        <span className="font-black text-[var(--dark)]">Fluō</span> · Your
        personal language companion
      </footer>

      {/* ── Auth Modal ─────────────────────────────── */}
      {showAuth && (
        <div
          className="modal-overlay fixed inset-0 z-50 flex items-center justify-center p-6"
          onClick={() => setShowAuth(false)}
        >
          <div className="w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <AuthScreen
              initialMode={authMode}
              onClose={() => setShowAuth(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
