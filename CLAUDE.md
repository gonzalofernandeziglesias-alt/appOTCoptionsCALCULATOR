# CLAUDE.md

## Project Overview

**appOTCoptionsCALCULATOR** — OTC (Over-The-Counter) options price calculator ("Calculadora precios opciones OTC"). A web application that computes pricing for OTC derivative options on precious metals using the Garman-Kohlhagen model, with live market data integration.

## Codebase Structure

```
appOTCoptionsCALCULATOR/
├── .claude/
│   ├── hooks/
│   │   └── session-start.sh       # Auto pip install on remote sessions
│   └── settings.json              # Claude Code hook configuration
├── .gitignore                     # Python cache/build exclusions
├── CLAUDE.md                      # AI assistant guidance (this file)
├── README.md                      # Project description
├── requirements.txt               # Python dependencies
├── app.py                         # Flask web application (routes & API)
├── pricing/
│   ├── __init__.py
│   └── black_scholes.py           # Garman-Kohlhagen pricing, Greeks, implied vol
├── market_data/
│   ├── __init__.py
│   └── fetcher.py                 # Live market data (Yahoo Finance, ECB, BoE)
├── templates/
│   └── index.html                 # Main UI template (Bootstrap 5)
└── static/
    ├── css/
    │   └── style.css              # Custom styles (dark blue theme)
    └── js/
        └── app.js                 # Frontend logic (AJAX, UI updates)
```

## Key Components

### Backend

- **app.py** — Flask app with 4 API endpoints:
  - `GET /` — Serves the calculator UI
  - `POST /api/calculate` — Computes option price, Greeks, breakeven, moneyness
  - `POST /api/implied-vol` — Derives implied volatility from a market premium
  - `POST /api/market-data` — Fetches live spot, volatility, and interest rates
  - `GET /api/debug` — Returns version and startup timestamp

- **pricing/black_scholes.py** — Garman-Kohlhagen pricing engine:
  - `gk_price()` — European option pricing
  - `gk_greeks()` — Delta, Gamma, Vega, Theta, Rho (domestic & foreign)
  - `implied_volatility()` — Newton-Raphson with bisection fallback
  - `breakeven_spot()` — Breakeven price at expiry

- **market_data/fetcher.py** — Multi-source market data with fallbacks:
  - Spot prices from Yahoo Finance (futures + FX conversion)
  - Historical volatility (3-month log-returns, annualized)
  - SLV options implied volatility as OTC reference
  - Risk-free rates from ECB (euro short-term rate, deposit facility rate), BoE, Yahoo Finance
  - Hardcoded defaults as last-resort fallback
  - Supported metals: XAG (Silver), XAU (Gold), XPT (Platinum), XPD (Palladium)
  - Supported currencies: EUR, USD, GBP, CHF, JPY

### Frontend

- **templates/index.html** — Bootstrap 5 responsive UI with cards for option details, market data, SLV IV panel, market premium comparison, and results display
- **static/js/app.js** — Vanilla JS with AJAX calls to all API endpoints, real-time UI updates (days to expiry, currency labels, OTC vol estimation), Greeks toggle (unit/total)
- **static/css/style.css** — Dark blue theme (#0d1b4a), monospace numeric displays, responsive layout

## Dependencies

```
flask>=3.0       # Web framework
numpy>=1.24      # Numerical computing
scipy>=1.10      # Normal distribution, optimization (brentq, Newton-Raphson)
requests>=2.28   # HTTP client for Yahoo Finance, ECB, BoE APIs
```

## Development Guidelines

### Language & Framework

- **Language**: Python 3
- **Framework**: Flask
- **Frontend**: Bootstrap 5, vanilla JavaScript (no build step)
- **Package manager**: pip

### Build & Run Commands

- **Install dependencies**: `pip install -r requirements.txt`
- **Run dev server**: `python app.py` (starts on http://localhost:5000)
- **Run tests**: `python -m pytest tests/` (no tests exist yet)

### Architecture Notes

- Stateless REST API — no database, all computation in-memory
- Static files use cache-busting query params (`?v=<timestamp>`)
- Market data fetching is resilient: primary source → fallback source → hardcoded defaults
- The `.claude/hooks/session-start.sh` hook auto-installs dependencies in remote Claude Code sessions

### Domain Context

This is a quantitative finance application. Key domain concepts:

- **OTC Options**: Derivative contracts traded directly between parties (not on exchanges)
- **Garman-Kohlhagen Model**: Extension of Black-Scholes for FX/commodity options with two interest rates (domestic r_d, foreign/lease r_f)
- **Greeks**: Delta, Gamma, Theta, Vega, Rho — sensitivities of option price to various parameters
- **Key Inputs**: Spot price (S), strike price (K), time to expiry (T in years), volatility (sigma, annualized %), domestic rate (r_d), foreign/lease rate (r_f)
- **SLV IV**: Implied volatility derived from iShares Silver Trust options chain, used as a reference for OTC silver volatility with an adjustable OTC spread

### Numerical Precision

- Use appropriate precision for financial calculations (avoid floating-point rounding issues)
- Validate all numerical inputs before computation
- Volatilities are in percentage points in the UI, converted to decimals (÷100) for calculations
- Time to expiry uses ACT/365 day-count convention

## Conventions for AI Assistants

### General Rules

- Read existing code before proposing changes
- Keep changes minimal and focused on the task at hand
- Do not add features, abstractions, or refactoring beyond what is requested
- Prefer simple, direct implementations over over-engineered solutions
- Validate at system boundaries (user input, API calls) but trust internal code

### Git Workflow

- Branch from `master`
- Write clear, descriptive commit messages
- Do not force-push or amend existing commits unless explicitly asked

### Code Style

- Follow the conventions already established in the codebase
- Do not add comments, docstrings, or type annotations to code you did not change
- Only add comments where logic is non-obvious

### Testing

- Write tests for new functionality when a test framework is in place
- Run the full test suite before committing when possible
- Do not mark tasks complete if tests are failing
