# CLAUDE.md

## Project Overview

**appOTCoptionsCALCULATOR** — OTC (Over-The-Counter) options price calculator ("Calculadora precios opciones OTC"). This application computes pricing for OTC derivative options using standard quantitative finance models.

## Codebase Structure

```
appOTCoptionsCALCULATOR/
├── CLAUDE.md                  # AI assistant guidance (this file)
├── README.md                  # Project description
├── requirements.txt           # Python dependencies
├── app.py                     # Flask web application (routes & API)
├── pricing/
│   ├── __init__.py
│   └── black_scholes.py       # Garman-Kohlhagen pricing, Greeks, implied vol
├── market_data/
│   ├── __init__.py
│   └── fetcher.py             # Live market data fetching (Yahoo Finance, ECB)
├── templates/
│   └── index.html             # Main UI template (Bootstrap 5)
└── static/
    ├── css/
    │   └── style.css           # Custom styles
    └── js/
        └── app.js              # Frontend logic (AJAX, UI updates)
```

## Development Guidelines

### Language & Framework

- **Language**: Python 3
- **Framework**: Flask
- **Frontend**: Bootstrap 5, vanilla JavaScript
- **Package manager**: pip

### Build & Run Commands

- **Install dependencies**: `pip install -r requirements.txt`
- **Run dev server**: `python app.py` (starts on http://localhost:5000)
- **Run tests**: `python -m pytest tests/` (when test framework is added)

### Domain Context

This is a quantitative finance application. Key domain concepts:

- **OTC Options**: Derivative contracts traded directly between parties (not on exchanges)
- **Option Pricing Models**: Black-Scholes, Binomial trees, Monte Carlo simulation
- **Greeks**: Delta, Gamma, Theta, Vega, Rho — sensitivities of option price to various parameters
- **Key Inputs**: Spot price, strike price, time to expiry, volatility, risk-free rate, dividend yield
- **Option Types**: Call/Put, European/American, Vanilla/Exotic (barriers, digitals, Asians, etc.)

### Numerical Precision

- Use appropriate precision for financial calculations (avoid floating-point rounding issues)
- Validate all numerical inputs before computation
- Document units and conventions (e.g., annualized volatility, day-count conventions)

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
