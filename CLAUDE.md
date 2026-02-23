# CLAUDE.md

## Project Overview

**appOTCoptionsCALCULATOR** — OTC (Over-The-Counter) options price calculator ("Calculadora precios opciones OTC"). This application computes pricing for OTC derivative options using standard quantitative finance models.

## Repository Status

This is a greenfield project. The repository currently contains only this guidance file and a README. All application code, tests, and configuration are yet to be implemented.

## Codebase Structure

```
appOTCoptionsCALCULATOR/
├── CLAUDE.md          # AI assistant guidance (this file)
├── README.md          # Project description
└── (no application code yet)
```

As the project grows, update this section to reflect the actual directory layout.

## Development Guidelines

### Language & Framework

Not yet decided. When chosen, document here:
- **Language**: TBD
- **Framework**: TBD
- **Package manager**: TBD

### Build & Run Commands

Document here once established:
- **Install dependencies**: TBD
- **Run dev server**: TBD
- **Build for production**: TBD
- **Run tests**: TBD
- **Run linter**: TBD

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
