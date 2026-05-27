# Fluō — AI Language Practice App 🌍

A multi-user, AI-powered web application for practicing any language through conversation. Upload your class notes, and the app extracts vocabulary and grammar, then generates personalised conversation sessions with text-to-speech and speech-to-text — all with per-user cost tracking and credit-based billing.

## Features

### 🔐 Authentication & Multi-User
- Email / password registration and login (JWT tokens)
- Per-user vocabulary, grammar, settings, and conversation history
- User panel showing credits balance and API usage

### 💳 Credit-Based Billing
- Every lesson pack costs **$1 + 2× raw OpenAI API cost**
- Real-time cost tracking per session (GPT-4o, Whisper, TTS)
- Buy credits via Stripe Checkout
- Usage history viewable in the user panel

### 📝 Note Extraction
- Upload images of your handwritten or printed notes
- Paste text notes directly
- AI (GPT-4o Vision) extracts vocabulary and grammar automatically
- All items start with "low" fluency level

### 📚 Vocabulary & Grammar Management
- View all extracted vocabulary and grammar concepts
- See fluency levels and practice statistics
- Filter by fluency level
- Delete items you don't want

### 🎯 Lesson Planning
- Automatically selects vocabulary and grammar with low fluency
- Generates conversation themes and goals
- Creates natural conversation scenarios

### 🎤 Interactive Conversation
- Text-to-speech for tutor responses
- Speech-to-text for your spoken responses
- Type responses if you prefer
- Natural conversation flow

### 📊 Analysis & Progress Tracking
- AI analyses your conversation transcript
- Identifies mistakes and correct usage
- Updates fluency scores automatically
- Adds new words you use to your vocabulary
- Tracks progress over time

## Setup

### Prerequisites
- Python 3.9+
- OpenAI API key (with access to GPT-4o, Whisper, and TTS)
- *(Optional)* PostgreSQL for production
- *(Optional)* Stripe account for billing

### Installation

1. **Clone / navigate to the project directory**

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS / Linux
   # or
   .\venv\Scripts\activate   # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**

   Create a `.env` file (or export in your shell):

   ```bash
   # ── Required ──────────────────────────────────────────
   OPENAI_API_KEY=sk-...

   # ── Auth ──────────────────────────────────────────────
   JWT_SECRET=replace-with-a-long-random-string
   # JWT_EXPIRATION_HOURS=72          # default 72

   # ── Database ──────────────────────────────────────────
   # SQLite (default — no config needed):
   # DATABASE_URL=sqlite:///./language_learning.db
   #
   # PostgreSQL (production):
   # DATABASE_URL=postgresql://user:pass@host:5432/fluo

   # ── Stripe (optional — billing disabled if unset) ─────
   # Obtain keys from https://dashboard.stripe.com/apikeys
   # STRIPE_SECRET_KEY=sk_test_...
   # STRIPE_PUBLISHABLE_KEY=pk_test_...
   # STRIPE_WEBHOOK_SECRET=whsec_...
   # STRIPE_PRICE_ID=price_...         # optional — auto-created if omitted

   # ── CORS (optional) ──────────────────────────────────
   # ALLOWED_ORIGINS=https://app.example.com,https://www.example.com
   ```

5. **Run database migration** *(only if upgrading from an existing database)*
   ```bash
   python migrate_db.py
   ```

6. **Run the application**
   ```bash
   python main.py
   ```

7. **Open in browser**
   Navigate to `http://localhost:8000` — register an account to get started.

### PostgreSQL Setup (Production)

```bash
# Uncomment Postgres drivers in requirements.txt
pip install asyncpg psycopg2-binary

# Set DATABASE_URL
export DATABASE_URL=postgresql://user:pass@localhost:5432/fluo
```

### Stripe Setup (Optional)

Fluō uses Stripe Checkout for one-time credit pack payments ($20 → 20 credits).

1. Get your **Secret key** and **Publishable key** from the [Stripe Dashboard → API keys](https://dashboard.stripe.com/apikeys)
2. Set `STRIPE_SECRET_KEY` and `STRIPE_PUBLISHABLE_KEY` in `.env`
3. The app **automatically creates** a Stripe Product + Price on first checkout if `STRIPE_PRICE_ID` is not set. You can also pre-create the product and set the env var.
4. Set up the webhook for payment confirmation:
   ```bash
   # Local testing with the Stripe CLI:
   stripe listen --forward-to localhost:8000/api/billing/webhook
   # Copy the webhook signing secret (whsec_...) into STRIPE_WEBHOOK_SECRET
   ```
5. In production, create a webhook endpoint in the Stripe Dashboard pointing to `https://yourdomain.com/api/billing/webhook` listening for `checkout.session.completed`.

## Usage

### 1. Register / Login
- Create an account with email and password
- You'll start with $0 credits; buy a credit pack to begin

### 2. Upload Notes
- Go to "Upload Notes" tab
- Upload an image of your notes or paste text
- The AI extracts vocabulary and grammar concepts

### 3. Review Your Content
- Check "Vocabulary" and "Grammar" tabs
- Delete any incorrect extractions

### 4. Start Practicing
- Go to "Practice" tab
- Adjust how many words/concepts to practice
- Click "Start Conversation"
- The tutor speaks in your target language — respond by speaking or typing

### 5. Review Analysis
- After the conversation ends, review your performance
- See which words you used correctly
- Learn from your mistakes
- Check updated fluency scores

## Architecture

```
┌────────────┐
│   Browser   │  JWT auth, Stripe Checkout redirect
└─────┬──────┘
      │  REST / multipart
      ▼
┌──────────────────────────────────────────────────────────┐
│                    FastAPI  (main.py)                     │
│  /api/auth/*   /api/billing/*   /api/* (protected)       │
├──────────────────────────────────────────────────────────┤
│  auth.py          cost_tracker.py        agents/         │
│  JWT + bcrypt     SessionCostTracker     NoteExtractor   │
│                   flush_to_db()          LessonPlanner   │
│                                          DialogueAgent   │
│                                          AnalysisAgent   │
│                                          LevelController │
├──────────────────────────────────────────────────────────┤
│           SQLAlchemy ORM  (database.py)                  │
│  Users │ Languages │ Vocabulary │ Grammar │ Conversations│
│  Settings │ UsageLogs                                    │
├──────────────────────────────────────────────────────────┤
│         SQLite (dev)  /  PostgreSQL (prod)               │
└──────────────────────────────────────────────────────────┘
```

## API Endpoints

### Auth & Billing

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Create a new account |
| `/api/auth/login` | POST | Login → JWT token |
| `/api/user/me` | GET | Current user info (email, credits) |
| `/api/billing/create-checkout-session` | POST | Start Stripe Checkout |
| `/api/billing/webhook` | POST | Stripe webhook handler |
| `/api/billing/usage` | GET | Usage / cost history |

### Learning (all require Bearer token)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload-notes` | POST | Upload notes (image or text) |
| `/api/vocabulary` | GET | Get vocabulary for active language |
| `/api/grammar` | GET | Get grammar for active language |
| `/api/start-lesson` | POST | Start a new practice session |
| `/api/conversation/{id}/respond` | POST | Send a response (audio or text) |
| `/api/conversation/{id}/end` | POST | End conversation & get analysis |
| `/api/stats` | GET | Get learning statistics |
| `/api/conversations` | GET | Get conversation history |
| `/api/languages` | GET | List user's languages |
| `/api/languages` | POST | Add a new language |
| `/api/languages/{id}/activate` | POST | Switch active language |
| `/api/settings/native-language` | GET/POST | Get or set native language |

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLite (dev) / PostgreSQL (prod) with SQLAlchemy
- **AI**: OpenAI GPT-4o (vision + chat), Whisper-1 (STT), TTS-1
- **Auth**: PyJWT + passlib (bcrypt)
- **Billing**: Stripe Checkout + Webhooks
- **Frontend**: Vanilla HTML/JS with Tailwind CSS

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | ✅ | — | OpenAI API key |
| `JWT_SECRET` | ✅ | `change-me-...` | Secret for signing JWT tokens |
| `JWT_EXPIRATION_HOURS` | — | `72` | Token lifetime in hours |
| `DATABASE_URL` | — | `sqlite:///./language_learning.db` | Database connection string |
| `STRIPE_SECRET_KEY` | — | — | Stripe secret key (from Dashboard → API keys) |
| `STRIPE_PUBLISHABLE_KEY` | — | — | Stripe publishable key |
| `STRIPE_WEBHOOK_SECRET` | — | — | Stripe webhook signing secret |
| `STRIPE_PRICE_ID` | — | *(auto-created)* | Stripe Price ID — auto-provisioned on first checkout if omitted |
| `ALLOWED_ORIGINS` | — | `*` | Comma-separated CORS origins |

## Tips for Best Results

1. **Upload clear notes** — The clearer your handwriting/photos, the better extraction
2. **Practice regularly** — Short daily sessions are better than long weekly ones
3. **Speak naturally** — Don't worry about mistakes, they help you learn
4. **Review analysis** — Pay attention to the corrections to improve

## License

MIT

## Contributing

Feel free to open issues or submit PRs!
