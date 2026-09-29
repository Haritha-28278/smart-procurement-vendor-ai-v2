# Smart Procurement Vendor AI 🤖📦

An AI-powered enterprise procurement assistant that helps businesses discover, evaluate, and select vendors intelligently using Anthropic Claude AI for matching, scoring, side-by-side comparison, and negotiation drafting.

---

## 🛠️ Strict Tech Stack

- **Frontend**: Plain HTML5, Modern CSS3, and Modular Vanilla JavaScript (ES6+). Styled with **Bootstrap 5 (via CDN)** and Bootstrap Icons. Analytics powered by **Chart.js (via CDN)**.
- **Backend**: **Python 3.11+ + FastAPI**.
- **Database**: **PostgreSQL** accessed via raw SQL queries using `psycopg2` (no ORM like SQLAlchemy — direct SQL queries with parameterized statements and `RealDictCursor`). Includes an automatic local SQLite fallback for instant offline/local development without needing a Postgres instance.
- **AI Engine**: **Claude API** (`anthropic` Python SDK). All AI interactions isolated in `backend/services/claude_service.py` with structured JSON output and caching.
- **Authentication**: JWT-based auth via `python-jose`, passwords hashed with `bcrypt`. Role-based access control (`Admin`, `Procurement Manager`, `Vendor`).

---

## 📁 Project Structure

```text
├── backend/
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py     # Direct SQL cursor manager & dialect handler
│   │   ├── schema.sql        # 5 core relational tables & indexes
│   │   └── seed.sql          # Sample data (3 users, 5 vendors, 2 RFQs, quotes, cached AI)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py           # Signup, login, JWT token verification, RBAC
│   │   ├── vendors.py        # Vendor registry CRUD
│   │   ├── rfq.py            # RFQ management & quote attachments
│   │   ├── quotes.py         # Vendor quote submissions & status transitions
│   │   └── ai_analysis.py    # AI matching, comparison, negotiation & analytics
│   ├── services/
│   │   ├── __init__.py
│   │   └── claude_service.py # Isolated Claude API calls, JSON extraction & heuristics
│   ├── __init__.py
│   └── main.py               # FastAPI entrypoint, lifespan startup, CORS, static mounts
├── frontend/
│   ├── css/
│   │   └── styles.css        # Custom B2B design system, glow cards, score pills
│   ├── js/
│   │   ├── api.js            # Modular API client, JWT management & toast notifications
│   │   ├── dashboard.js      # Chart.js analytics & KPI metric updates
│   │   ├── vendors.js        # Vendor registry CRUD, modals & debounced search
│   │   ├── rfq.js            # RFQ workspace, quote submissions, Claude AI matching
│   │   └── compare.js        # Top 3 side-by-side comparison & Claude executive summary
│   └── pages/
│       ├── login.html        # Sign in, account registration, quick demo logins
│       ├── dashboard.html    # Executive procurement analytics & spend trends
│       ├── vendors.html      # Supplier directory & SLA certifications
│       ├── rfq.html          # RFQ evaluation, Claude AI scoring & negotiation
│       └── compare.html      # Side-by-side vendor comparison matrix
├── .env.example              # Environment variables template
├── requirements.txt          # Python dependencies
├── Dockerfile                # Production containerization
├── docker-compose.yml        # Multi-container orchestration (FastAPI + PostgreSQL)
└── README.md                 # System documentation
```

---

## 🔑 Pre-Seeded Demo Accounts

All pre-seeded demo accounts use password: `password123`

| Email | Role | Access Level |
|---|---|---|
| `admin@smartprocure.ai` | **Admin** | Full system access, vendor management, RFQs, AI triggers |
| `manager@smartprocure.ai` | **Procurement Manager** | Create RFQs, evaluate quotes, negotiate with vendors |
| `vendor@apexlogistics.com` | **Vendor** | View RFQs and submit quotation bids |

*(Quick-fill buttons for these accounts are available directly on the login page).*

---

## 🚀 Quickstart & Setup

### Option 1: Direct Local Run (Recommended for fast testing)

1. **Clone & Navigate:**
   ```bash
   cd "Smart Procurement Vendor AI"
   ```

2. **Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Add your `ANTHROPIC_API_KEY` in `.env` if you have one. *(If not set or in offline mode, the built-in intelligent heuristic engine will generate realistic scores, reasoning, risk flags, and negotiation drafts automatically).*

4. **Start the FastAPI Server:**
   ```bash
   python backend/main.py
   # Or using uvicorn directly:
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Open in Browser:**
   Visit **[http://localhost:8000](http://localhost:8000)** (redirects directly to `/pages/login.html`).

---

### Option 2: Docker Compose (Full Stack with PostgreSQL 16)

1. Make sure Docker is running on your machine.
2. Run:
   ```bash
   docker-compose up --build
   ```
3. Visit **[http://localhost:8000](http://localhost:8000)**.
   PostgreSQL 16 will start automatically with schema and seed data loaded.

---

## 🌟 Core Features Walkthrough

### 1. SQL Schema (`backend/db/schema.sql`)
- `users`: Role-based authentication (`Admin`, `Procurement Manager`, `Vendor`).
- `vendors`: Supplier directory (name, category, pricing tier, certifications, past performance SLA, rating, contact).
- `rfqs`: Request for quotations with title, category, budget, requirements, deadline, and status.
- `quotes`: Supplier bids with quote amounts, delivery timeline (days), proposal details, and status.
- `ai_analysis`: Cached Claude AI matching scores (`0-100`), reasoning text, and risk flags JSON array per RFQ+vendor pair.

### 2. Authentication & Security
- Passwords hashed with `bcrypt` with salt rounds.
- JWT tokens signed with `HS256` algorithm using `python-jose`.
- Client requests automatically include `Authorization: Bearer <token>`.
- Token expiration detection with auto-redirection to login.

### 3. Vendor Registry
- Live search by name, category, location, and certifications.
- Filter by industry domain.
- Add/Edit vendor modal with validation.
- Detailed vendor dossier modal showing historical SLA reliability.

### 4. RFQ Workspace
- Create new RFQs with budget caps and delivery deadlines.
- View submitted bids, price variance vs budget ceiling.
- Vendor quotation submission modal.

### 5. Claude AI Vendor Matching
- Button to trigger Claude evaluation against all suppliers.
- Structured output: `match_score` (0-100), `reasoning`, and `risk_flags`.
- Visual score pills (High: 85+, Medium: 70-84, Risk: <70).
- Automatic caching in `ai_analysis` to prevent redundant API calls.

### 6. Side-by-Side Comparison (`compare.html`)
- Side-by-side comparison of top 3 vendor candidates.
- Claude AI generated **Executive Summary** identifying optimal choice and key trade-offs.
- Visual crown indicator on the recommended winner.
- Side-by-side evaluation of price variance, SLA rating, certifications, and risk flags.

### 7. AI Commercial Negotiation Assistant
- Select negotiation strategy: *Balanced*, *Aggressive Cost-Savings (BAFO)*, or *Collaborative Partnership*.
- Claude drafts an email targeting budget alignment and milestones.
- Fully editable subject and body with one-click copy to clipboard.

### 8. Analytics Dashboard (`dashboard.html`)
- **Chart.js** spend trends: Allocated Budget vs Actual Spend vs AI Savings.
- Category distribution doughnut chart.
- Key metrics: Total Budget, AI Cost Savings, Active RFQs, and Average Match Score.
- Top rated vendor leaderboard.

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Register new user account |
| `POST` | `/api/auth/login` | Authenticate user & issue JWT |
| `GET` | `/api/auth/me` | Fetch authenticated user profile |
| `GET` | `/api/vendors` | List suppliers (filters: `category`, `search`) |
| `POST` | `/api/vendors` | Create new supplier |
| `PUT` | `/api/vendors/{id}` | Update supplier |
| `DELETE` | `/api/vendors/{id}` | Delete supplier |
| `GET` | `/api/rfq` | List RFQs |
| `POST` | `/api/rfq` | Create RFQ |
| `GET` | `/api/rfq/{id}` | Get RFQ details with quotes & AI analysis |
| `POST` | `/api/quotes` | Submit quote for an RFQ |
| `PATCH`| `/api/quotes/{id}/status` | Update quote status (Shortlisted, Accepted, Rejected) |
| `POST` | `/api/ai/match/{rfq_id}` | Run Claude AI matching on vendors |
| `GET` | `/api/ai/compare/{rfq_id}` | Get top 3 comparison & Claude summary |
| `POST` | `/api/ai/negotiate` | Generate commercial negotiation email draft |
| `GET` | `/api/ai/analytics` | Aggregated metrics for Chart.js dashboard |
