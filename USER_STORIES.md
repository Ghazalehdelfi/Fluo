# Fluō — Key User Stories (QA Reference)

This document describes the **ideal behaviour** of the Fluō web application as a set of user stories with acceptance criteria. It is intended to drive an agentic QA loop: each story should be verifiable end-to-end through the UI (and, where noted, the API).

**Personas**
- **Guest** — not authenticated.
- **Student** — authenticated user with role `student` (default).

For authentication checks, you can use this creds:
user = suzan
pass = 96KQmrTik1
---

## 1. Authentication & Accounts

### US-1.1 — Register as a new user
**As a** Guest, **I want to** create an account with my email and password, **so that** I can save my learning progress.

- The auth screen offers "Sign Up" with email, password (min 8 chars), confirm password, and a role selector (Student / Teacher, default Student).
- Submitting valid details creates the account, signs me in immediately, and grants a **$5 welcome credit bonus**.
- email should be authenticated with login flow, so users cannot use invalid emails to create accounts
- Duplicate email, weak password (<8 chars), or mismatched confirmation each show a specific inline error and do not create an account.
- On success, Students land on the dashboard/onboarding; Teachers land on the Classes page.

### US-1.2 — Log in and stay logged in
**As a** returning user, **I want to** log in with my email and password, **so that** I can resume where I left off.

- Valid credentials issue a JWT (72h expiry) stored in local storage; refreshing the page keeps me logged in.
- Invalid credentials show a clear error and do not reveal which field was wrong.
- When my token expires, the next API call logs me out cleanly and redirects to the auth screen.

### US-1.3 — Log out
**As a** logged-in user, **I want to** log out, **so that** my account is secure on shared devices.

- Logging out clears the token and all cached per-language data, and returns me to the landing/auth view.

---

## 2. Language Management & Onboarding

### US-2.1 — Add a language to learn
**As a** Student, **I want to** add a language from the supported list (Turkish, Spanish, French, Persian, Korean, Japanese, German), **so that** I can start learning it.

- A first-time user with no languages is guided through an onboarding language picker.
- "Add Language" opens a modal of available languages; adding one creates it and makes it selectable.
- Re-adding a previously removed language reactivates it with its data intact (no duplicates).

### US-2.2 — Switch and remove languages
**As a** Student, **I want to** switch between my languages and remove ones I no longer study, **so that** my workspace stays relevant.

- The sidebar/language selector switches the active language; all pages (vocab, grammar, practice, stats) reflect the selection.
- Removing a language asks for confirmation and soft-deletes it (data preserved, hidden from UI).

### US-2.3 — Set default and native language
**As a** user, **I want to** set a default language and my native language, **so that** the app opens on the right language and gives translations/hints in a language I understand.

- Settings allow choosing a default language (must be one of my active languages) and a native language.
- The default language is preselected on login; the native language is used for translations and hints everywhere.

---

## 3. Note Upload & AI Extraction

### US-3.1 — Extract vocabulary and grammar from notes
**As a** Student, **I want to** upload photos/PDFs of my class notes or paste text, **so that** the AI extracts vocabulary and grammar for me.

- The Upload page accepts images (JPG/PNG), PDFs, and pasted text; multiple files can be processed with visible per-file progress.
- Text-based PDFs use the embedded text layer; scanned/handwritten PDFs are rendered to images (max 10 pages) for vision extraction.
- Extraction requires ≥ $1 credit; insufficient balance shows a clear prompt to buy credits.

### US-3.2 — Review and edit extracted items before saving
**As a** Student, **I want to** review, edit, and delete extracted items, **so that** only correct content enters my library.

- The review modal lists extracted vocabulary (word, translation, example) and grammar (concept, description, examples) with inline-editable fields.
- I can delete individual rows and save everything with one "Save All" action.
- Saved items appear in my Vocabulary/Grammar lists with fluency level "low".
- Ambiguous grammar matches appear as "pending" items I can resolve by choosing an existing concept.

---

## 4. Vocabulary & Grammar Library

### US-4.1 — Browse and filter my library
**As a** Student, **I want to** view all my vocabulary and grammar with fluency levels and practice stats, **so that** I know what to focus on.

- Tables show word/concept, translation/description, examples, fluency (low/medium/high with visual indicator), and times practiced/correct.
- I can filter by fluency level.

### US-4.2 — Edit and delete items
**As a** Student, **I want to** correct or remove library items, **so that** my data stays accurate.

- Editing updates word/translation/example (vocab) or name/description/examples (grammar) and persists immediately.
- Deleting asks for confirmation and removes the item from future practice.

### US-4.3 — View a grammar detail card and hear pronunciation
**As a** Student, **I want to** open an AI-generated detail card for a grammar concept and hear words spoken, **so that** I can study them in depth.

- The detail card shows an explanation, rules, and examples for the concept.
- Clicking a word plays its pronunciation via text-to-speech.

---

## 5. Flashcards

### US-5.1 — Practice vocabulary with flashcards
**As a** Student, **I want to** run a flashcard session over my vocabulary, **so that** I can memorise words. (Free — no credits required.)

- Setup lets me choose direction (target→native or native→target) and fluency filter, and shows how many cards match.
- Cards flip on click; I mark each "Got it" or "Again"; a streak counter and "X of Y" progress are visible.
- Results show my score %, and each answer updates the word's practice stats.
- With zero vocabulary, flashcards are unavailable with a helpful empty state.

---

## 6. Placement Test

### US-6.1 — Take an adaptive placement test
**As a** Student with a new language, **I want to** take a placement test, **so that** the app knows my CEFR level. (Free — no credits required.)

- A language with no vocabulary and no grammar routes me to the placement test.
- The test asks 3 questions per CEFR level (A1→C2); scoring ≥60% advances me to the next level, otherwise the test ends.
- Questions include multiple choice, translation, and fill-in-the-blank; a "Don't Know" option is always available; feedback appears after each answer.
- For Persian, a romanization (Finglish) toggle/display is available.

### US-6.2 — Save placement results
**As a** Student, **I want to** save my placement outcome, **so that** my level and starter content match my ability.

- The results view shows per-level scores; "Save Results & Continue" stores my level, pre-populates level-appropriate vocabulary and grammar, and redirects to the dashboard.

---

## 7. Conversation Practice (Lessons & Scenarios)

### US-7.1 — Start a lesson
**As a** Student, **I want to** start an AI conversation lesson built from my weakest vocabulary and grammar, **so that** I practice what I need most.

- Setup offers Lesson mode (pick a clustered topic or let the AI choose) and Scenario mode (my own custom prompt), plus how many words (default 5) and grammar concepts (default 1) to target.
- Starting requires ≥1 vocabulary item and ≥ $1 credit; otherwise I get a clear explanation.
- The tutor opens the conversation in the target language with audio (TTS) and text.

### US-7.2 — Converse by voice or text
**As a** Student, **I want to** respond by speaking or typing, **so that** I can practice naturally.

- I can type a response or record audio (transcribed via speech-to-text); the tutor replies with audio + text each turn.
- The message history auto-scrolls; the tutor's language stays appropriate to my level.
- Sessions expire after ~30 minutes of inactivity with a graceful end state.

### US-7.3 — End the lesson and review analysis
**As a** Student, **I want to** end the lesson and receive feedback, **so that** I learn from my mistakes.

- Ending produces: overall feedback, which target words/grammar I used correctly, my mistakes with corrections, the full transcript, and the session cost in USD.
- Fluency levels of practiced items update automatically; new words I used may be added to my vocabulary.
- The session's cost is deducted from my credits (2× raw API cost) and visible in my usage history.

---

## 8. Grammar Practice

### US-8.1 — Drill a grammar concept
**As a** Student, **I want to** practice a specific grammar concept with generated exercises, **so that** I can master it.

- From a grammar concept I can start a practice session of 10 exercises (multiple choice, translation, fill-in-the-blank) matched to my level and the concept's fluency.
- Each answer gets immediate correct/incorrect feedback with an explanation before moving on; progress "Q n/10" is visible.
- The results view shows my final score and a per-question breakdown; the concept's fluency and stats update.
- Requires ≥ $1 credit; cost is deducted at session end.

---

## 9. Dashboard & Progress

### US-9.1 — See my progress at a glance
**As a** Student, **I want to** see per-language stats and quick actions, **so that** I can decide what to do next.

- The dashboard shows total vocabulary, grammar, and conversation counts, plus fluency breakdowns (low/medium/high) for the active language.
- Quick actions link to Upload, Lesson, Grammar practice, Flashcards, and Placement.
- My credit balance is always visible.

### US-9.2 — Review conversation history
**As a** Student, **I want to** revisit past conversations and their analyses, **so that** I can track improvement over time.

- History lists past sessions with date, transcript, analysis, and cost.

---

## 10. Billing & Credits

### US-13.1 — Buy credits
**As a** user, **I want to** buy credit packs ($5 / $10 / $20) via Stripe Checkout, **so that** I can keep using paid features.

- "Buy Credits" opens Stripe Checkout; successful payment credits my account and returns me with a success indication; cancelling returns me without changes.
- The balance updates without needing to re-login.

### US-13.2 — Understand my spending
**As a** user, **I want to** see my credit balance and per-session usage history, **so that** I know where my money goes.

- The user panel shows current balance and a usage/cost history (date, activity, cost).
- Every paid session displays its exact cost at the end.

---

## 11. Cross-Cutting Behaviour

### US-14.1 — Graceful handling of insufficient credits
**As a** user with low balance, **I want** paid actions to be blocked with a clear explanation and a path to buy credits, **so that** I'm never surprised by a failure mid-task.

### US-14.2 — Rate limiting feedback
**As a** user, **I want** clear feedback when I hit a rate limit, **so that** I know to wait rather than retry frantically.

### US-14.3 — Role-based access
**As the system**, **I must** restrict teacher-only pages/endpoints to teachers and student homework to enrolled students, **so that** data and capabilities are properly isolated.

### US-14.4 — Multi-language data isolation
**As a** user with multiple languages, **I want** vocabulary, grammar, stats, and practice to be strictly per-language, **so that** switching languages never mixes content.

### US-14.5 — Responsive & resilient UI
**As a** user on any device, **I want** a working mobile sidebar/navigation and UI that recovers cleanly from network errors, **so that** I can learn anywhere.

## 12. API expectations**
- All authenticated API calls require a valid `Authorization: Bearer <JWT>` header; an expired/invalid token (401) logs the user out and returns them to the auth screen.
- Loading states are shown during AI operations; errors surface as user-readable messages, not silent failures or stack traces.
- Credit-gated actions (upload, conversation, grammar practice) require a balance ≥ $1.00 and return a clear "insufficient credits" state (HTTP 402) otherwise.
- Rate limits return HTTP 429 with a retry-friendly message (register: 5/min/IP, login: 10/min/IP, lesson start: 10/min/user, upload: 30/min/user, grammar practice: 30/min/user).