# Portfolio Market Simulation & Intelligent Evaluation System

Local-first classroom platform for Portfolio Theory & Risk Management. PM + Assistant operate as **one team** through one shared team account.

## Features
- Investor/customer management and mandates
- Six reusable investor-mandate cards with return, risk, equity, liquidity, restriction and horizon rules
- Six instructor-only event scenario packs with learning objectives, expected relationships and teaching notes
- Required round-by-round decision evidence: action, justification, expected outcome, main risk, confidence and mandate connection
- Instructor-only debrief timeline combining events, decisions, portfolio values, risk/compliance and benchmark context
- Evaluation diagnostics for turnover, HOLD decisions and decision-evidence completion, plus written instructor override
- Asset master: stocks, T-bills, commercial bills, coupon bonds
- Real-data adapter endpoint (Stooq-compatible CSV where available) + professional simulated market feed
- Admin market shocks and interest/yield events
- T-bill, discount bill, coupon bond pricing; duration and sensitivity
- Portfolio creation, lock, immutable snapshots, buy/sell/hold/rebalance journal
- Mark-to-market value, P/L, return, volatility, Sharpe, max drawdown, HHI concentration
- Benchmark comparison and mandate compliance
- Simulation lifecycle: draft, start, pause, resume, end/freeze
- Hidden Organizer Evaluation page with weights locked at simulation start
- Immutable decision journal plus audit trail for critical actions
- PBKDF2 password authentication with expiring bearer sessions
- Admin/team role authorization and strict team portfolio isolation
- Atomic multi-asset rebalancing with rollback on invalid legs
- End-of-simulation team reports and risk-aware comparison API
- Six configurable PSX classroom assets: UBL, EFERT, NRL, ATRL, POL and APL
- Seeded, economically differentiated rate/oil/growth/dividend/market event responses
- Persisted simulation rounds and per-asset price histories
- Correlation-aware portfolio volatility and energy-concentration warnings
- Evidence-based AI-ready narrative (deterministic fallback; no fabricated numbers)
- Historical feature export for future ML
- SQLite persistence, REST API, responsive financial dashboard

## Run
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

On this Windows machine a repaired environment is available at `.runtime`:
```powershell
.\.runtime\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Demo
The local demo uses `admin / admin123` for the instructor and `teamalpha / team1234` for the portfolio-management team. The bootstrap endpoint disables itself after accounts exist. Portfolio managers can create and save separate investor records from the mandate cards. Instructor scenario answers and evaluation stay hidden from team accounts.

## Tests
```bash
pytest -q
```

The database location can be overridden for testing or deployment with
`PORTFOLIO_DB_URL` (for example, a PostgreSQL SQLAlchemy URL).

## Market event model

PSX simulation prices are separate from reference prices. A controlled response is calculated from event direction and magnitude, beta, the relevant asset sensitivity, sector sensitivity, volatility multiplier, severity, and small seeded noise. This keeps economic relationships visible while avoiding identical or perfectly predictable moves. Instructor quick controls include rate, oil, boom/crash, growth/slowdown, dividend and refinery-sector events, plus custom shocks and market reset.

The six-stock asset master is defined in `app/services/asset_master.py`; event mathematics is isolated in `app/services/market_engine.py`. The UI always labels these values as simulation prices, not live PSX quotations.

## Important
Real market data is provider-dependent. The included adapter demonstrates permitted public HTTP integration when available; it never labels simulated data as live. For PSX production use, connect a licensed/permitted feed. Policy rate and market yields are separate variables.
