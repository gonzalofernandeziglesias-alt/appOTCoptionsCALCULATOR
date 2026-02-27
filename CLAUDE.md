# CLAUDE.md

## Project Overview

**appOTCoptionsCALCULATOR** — OTC (Over-The-Counter) options price calculator ("Calculadora precios opciones OTC"). A single-page web app that prices European vanilla OTC options on FX pairs and precious metals using the Garman-Kohlhagen model. It fetches live market data (spot, rates, volatility) from free sources and lets users compare theoretical prices against actual market premiums.

## Codebase Structure

```
appOTCoptionsCALCULATOR/
├── CLAUDE.md                  # AI assistant guidance (this file)
├── README.md                  # Project description (minimal)
├── .gitignore                 # Python bytecode, .env, build artifacts
├── requirements.txt           # Python dependencies (flask, numpy, scipy, requests)
├── app.py                     # Flask web application (routes & JSON API)
├── pricing/
│   ├── __init__.py            # Empty
│   └── black_scholes.py       # Garman-Kohlhagen pricing, Greeks, implied vol, breakeven
├── market_data/
│   ├── __init__.py            # Empty
│   └── fetcher.py             # Live market data fetching (Yahoo Finance, ECB, BoE)
├── templates/
│   └── index.html             # Single-page UI template (Bootstrap 5, Jinja2)
├── static/
│   ├── css/
│   │   └── style.css          # Custom styles (CSS variables, responsive)
│   └── js/
│       └── app.js             # Frontend logic (AJAX calls, UI updates, Greeks toggle)
└── .claude/
    ├── settings.json          # Claude Code hooks configuration
    └── hooks/
        └── session-start.sh   # Auto-installs pip dependencies in remote sessions
```

## Dependencies

Defined in `requirements.txt`:
- **flask** >= 3.0 — Web framework
- **numpy** >= 1.24 — Numerical computation
- **scipy** >= 1.10 — Statistical functions (`norm.cdf`, `norm.pdf`, `brentq`)
- **requests** >= 2.28 — HTTP client for market data APIs

No test framework is configured yet. No database.

## Development Guidelines

### Language & Framework

- **Language**: Python 3
- **Framework**: Flask (single `app.py`, no blueprints)
- **Frontend**: Bootstrap 5.3.2 (CDN), vanilla JavaScript (no build step)
- **Package manager**: pip

### Build & Run Commands

- **Install dependencies**: `pip install -r requirements.txt`
- **Run dev server**: `python app.py` (starts on http://localhost:5000, debug mode, binds 0.0.0.0)
- **Run tests**: `python -m pytest tests/` (no tests directory exists yet)

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves the single-page UI (`index.html`) |
| POST | `/api/calculate` | Prices an option and returns Greeks, breakeven, moneyness, and optional market comparison |
| POST | `/api/implied-vol` | Calculates implied volatility from a market premium using Newton-Raphson with bisection fallback |
| POST | `/api/market-data` | Fetches live spot, rates, historical vol, and SLV implied vol for a currency pair |
| GET | `/api/debug` | Returns server version and start timestamp |

All POST endpoints accept and return JSON. Rates and volatility are exchanged as **percentages** (e.g., 2.5 for 2.5%) between frontend and API; the backend converts to decimals internally.

### Domain Context

This is a quantitative finance application. Key domain concepts:

- **OTC Options**: Derivative contracts traded directly between parties (not on exchanges)
- **Garman-Kohlhagen Model**: Extension of Black-Scholes for FX/commodity options — the only pricing model currently implemented. Accounts for separate domestic and foreign risk-free rates
- **Greeks**: Delta, Gamma, Vega, Theta, Rho_d (domestic), Rho_f (foreign) — sensitivities of option price to various parameters. Vega is per 1% vol change, Theta is per calendar day, Rho is per 1% rate change
- **Key Inputs**: Spot price (domestic per 1 unit foreign), strike price, valuation/expiry dates, annualized volatility, domestic risk-free rate, foreign risk-free rate (or lease rate for metals), notional amount
- **Supported Instruments**: European vanilla Call/Put on FX pairs (EUR, USD, GBP, CHF, JPY) and precious metals (XAG, XAU, XPT, XPD)
- **Implied Volatility**: Solved via Newton-Raphson (Brenner-Subrahmanyam initial guess) with bisection fallback
- **SLV Implied Vol**: ATM implied volatility extracted from SLV (iShares Silver Trust) options chain on Yahoo Finance, used as a reference for silver OTC volatility with a configurable OTC spread

### Market Data Sources

- **Spot prices**: Yahoo Finance v8 chart API. Metals use futures tickers (SI=F, GC=F, PL=F, PA=F) crossed with FX rates
- **Interest rates**: ECB (€STR, deposit facility rate) for EUR, Yahoo ^IRX for USD, BoE Bank Rate for GBP. Hardcoded defaults as fallback
- **Historical volatility**: Yahoo Finance 3-month daily closes, log-return std dev × √252. Outlier filter removes >10% daily moves (futures rollover noise)
- **SLV options IV**: Yahoo Finance v7 options API. Picks expiry closest to the user's tenor, finds ATM calls within 5% of spot, computes IV via Brent's method, reports median

### Numerical Precision

- Use appropriate precision for financial calculations (avoid floating-point rounding issues)
- Validate all numerical inputs before computation
- Time to expiry uses ACT/365 day count convention (`days / 365.0`)
- API results are rounded: price per unit to 6 decimals, total premium to 2, Greeks (unit) to 8, Greeks (total) to 4

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
- Single-letter math variables are acceptable in pricing code (S, K, T, r_d, r_f, sigma) — this matches financial convention
- Do not add comments, docstrings, or type annotations to code you did not change
- Only add comments where logic is non-obvious

### Testing

- Write tests for new functionality when a test framework is in place
- Run the full test suite before committing when possible
- Do not mark tasks complete if tests are failing
