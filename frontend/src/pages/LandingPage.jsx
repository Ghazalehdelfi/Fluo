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
            Your personal language companion
          </div>
          <h1 className="mt-6 text-5xl font-black leading-[1.08] tracking-tight text-[var(--dark)] md:text-6xl lg:text-[4.5rem]">
            Learn a language
            <br />
            <span className="text-[var(--primary)]">
              from your own material.
            </span>
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
        </div>
      </section>

      {/* ── Who are you? ───────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 pb-4 md:px-10">
        <h2 className="text-center text-3xl font-black tracking-tight text-[var(--dark)] md:text-4xl">
          Who is Fluō for?
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-center text-base text-[var(--accent1)]">
          Whether you're learning solo or running a class, Fluō fits your
          workflow.
        </p>
        <div className="mt-10 grid gap-5 md:grid-cols-2">
          <div
            className="group cursor-pointer rounded-3xl border border-[rgba(67,101,101,0.18)] bg-white p-8 transition-all duration-200 hover:-translate-y-1 hover:shadow-[0_16px_40px_rgba(17,56,44,0.12)]"
            onClick={() =>
              document
                .getElementById("self-learner")
                .scrollIntoView({ behavior: "smooth" })
            }
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--primary-container)]">
              <span
                className="material-symbols-outlined text-[var(--primary)]"
                style={{ fontSize: 26 }}
              >
                person
              </span>
            </div>
            <h3 className="mt-5 text-xl font-black text-[var(--dark)]">
              Self Learner
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--accent1)]">
              You study independently — with a tutor, a course, or just from
              books and shows. Fluō becomes your always-on practice partner that
              works from <em>your</em> material, not a preset curriculum.
            </p>
            <div className="mt-5 flex items-center gap-1 text-sm font-semibold text-[var(--primary)] transition-all group-hover:gap-2">
              See how it works
              <span
                className="material-symbols-outlined"
                style={{ fontSize: 18 }}
              >
                arrow_forward
              </span>
            </div>
          </div>

          <div
            className="group cursor-pointer rounded-3xl border border-[rgba(67,101,101,0.18)] bg-white p-8 transition-all duration-200 hover:-translate-y-1 hover:shadow-[0_16px_40px_rgba(17,56,44,0.12)]"
            onClick={() =>
              document
                .getElementById("teachers")
                .scrollIntoView({ behavior: "smooth" })
            }
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--tertiary-container)]">
              <span
                className="material-symbols-outlined text-[var(--primary)]"
                style={{ fontSize: 26 }}
              >
                school
              </span>
            </div>
            <h3 className="mt-5 text-xl font-black text-[var(--dark)]">
              Language Teacher
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--accent1)]">
              You teach classes or give private lessons. Fluō lets you assign
              structured practice homework and see exactly how each student is
              progressing between sessions.
            </p>
            <div className="mt-5 flex items-center gap-1 text-sm font-semibold text-[var(--primary)] transition-all group-hover:gap-2">
              See how it works
              <span
                className="material-symbols-outlined"
                style={{ fontSize: 18 }}
              >
                arrow_forward
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* ── Self Learner Section ────────────────────── */}
      <section
        id="self-learner"
        className="mt-16 bg-[var(--surface-container-low)] py-16"
      >
        <div className="mx-auto max-w-6xl px-5 md:px-10">
          <div className="mb-3 inline-flex items-center rounded-full bg-[var(--primary-container)] px-4 py-1.5">
            <span className="text-xs font-bold uppercase tracking-widest text-[var(--primary)]">
              For self learners
            </span>
          </div>
          <h2 className="mt-2 max-w-2xl text-3xl font-black leading-tight tracking-tight text-[var(--dark)] md:text-4xl">
            A companion that learns <em>with</em> your material, not despite it.
          </h2>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--accent1)]">
            Most apps ignore what you're actually studying. Fluō does the
            opposite — everything starts from your own notes, and every practice
            session pulls from what you've genuinely encountered.
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

      {/* ── Teacher Section ─────────────────────────── */}
      <section
        id="teachers"
        className="bg-[var(--surface-container-low)] py-16"
      >
        <div className="mx-auto max-w-6xl px-5 md:px-10">
          <div className="mb-3 inline-flex items-center rounded-full bg-[var(--tertiary-container)] px-4 py-1.5">
            <span className="text-xs font-bold uppercase tracking-widest text-[var(--primary)]">
              For teachers
            </span>
          </div>
          <h2 className="mt-2 max-w-2xl text-3xl font-black leading-tight tracking-tight text-[var(--dark)] md:text-4xl">
            Give your students a practice partner between sessions.
          </h2>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--accent1)]">
            Students forget most of what they learn within 24 hours without
            reinforcement. Fluō turns your curriculum into structured daily
            practice so your teaching actually sticks.
          </p>
          <div className="mt-10 grid gap-5 sm:grid-cols-3">
            {TEACHER_FEATURES.map((f) => (
              <div
                key={f.title}
                className="rounded-2xl border border-[rgba(67,101,101,0.12)] bg-white p-5 transition-all hover:-translate-y-0.5 hover:shadow-[0_8px_24px_rgba(17,56,44,0.08)]"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--tertiary-container)]">
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
              Set up a class
            </button>
          </div>
        </div>
      </section>

      {/* ── Bottom CTA ─────────────────────────────── */}
      <section className="relative overflow-hidden py-24">
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-[rgba(114,168,151,0.14)] via-transparent to-[rgba(241,204,131,0.14)]" />
        <div className="relative mx-auto max-w-2xl px-5 text-center md:px-10">
          <h2 className="text-4xl font-black leading-tight tracking-tight text-[var(--dark)] md:text-5xl">
            Start speaking more.
            <br />
            Starting today.
          </h2>
          <p className="mx-auto mt-5 max-w-lg text-base leading-relaxed text-[var(--accent1)]">
            Upload your first set of notes, build your knowledge base, and try a
            live conversation — all in under five minutes.
          </p>
          <button
            onClick={() => openAuth("signup")}
            className="btn-primary mt-8 rounded-2xl px-8 py-4 text-base font-bold"
          >
            Create your free account
          </button>
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
          className="modal-overlay fixed inset-0 z-50 flex items-center justify-center p-4"
          onClick={() => setShowAuth(false)}
        >
          <div onClick={(e) => e.stopPropagation()}>
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
