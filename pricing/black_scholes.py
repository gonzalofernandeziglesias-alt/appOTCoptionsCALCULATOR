"""
Garman-Kohlhagen model for FX/Commodity OTC option pricing.

Extension of Black-Scholes for options on foreign exchange and precious metals.
Supports European vanilla options with full Greeks calculation and implied
volatility solving.
"""

import numpy as np
from scipy.stats import norm


def gk_price(S, K, T, r_d, r_f, sigma, option_type='call'):
    """
    Garman-Kohlhagen option pricing.

    Parameters:
        S:     Spot price (domestic per foreign, e.g. EUR per 1 XAG)
        K:     Strike price (same units as S)
        T:     Time to expiry in years
        r_d:   Domestic continuous risk-free rate (e.g. EUR rate)
        r_f:   Foreign continuous risk-free rate (e.g. XAG lease rate)
        sigma: Annualized volatility
        option_type: 'call' or 'put'

    Returns:
        Option price per unit of foreign currency (e.g. EUR per 1 XAG)
    """
    if T <= 0:
        if option_type == 'call':
            return max(S - K, 0.0)
        else:
            return max(K - S, 0.0)

    if sigma <= 0:
        raise ValueError("Volatility must be positive")

    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r_d - r_f + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    if option_type == 'call':
        price = (S * np.exp(-r_f * T) * norm.cdf(d1)
                 - K * np.exp(-r_d * T) * norm.cdf(d2))
    else:
        price = (K * np.exp(-r_d * T) * norm.cdf(-d2)
                 - S * np.exp(-r_f * T) * norm.cdf(-d1))

    return float(price)


def gk_greeks(S, K, T, r_d, r_f, sigma, option_type='call'):
    """
    Calculate Greeks for the Garman-Kohlhagen model.

    Returns dict with:
        delta     – sensitivity to spot price
        gamma     – sensitivity of delta to spot
        vega      – sensitivity to 1% change in volatility
        theta     – daily time decay (per calendar day)
        rho_d     – sensitivity to 1% change in domestic rate
        rho_f     – sensitivity to 1% change in foreign rate
    """
    if T <= 0:
        intrinsic_call = S > K
        intrinsic_put = S < K
        return {
            'delta': 1.0 if (option_type == 'call' and intrinsic_call) else
                     (-1.0 if (option_type == 'put' and intrinsic_put) else 0.0),
            'gamma': 0.0,
            'vega': 0.0,
            'theta': 0.0,
            'rho_d': 0.0,
            'rho_f': 0.0,
        }

    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r_d - r_f + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    nd1 = norm.pdf(d1)
    Nd1 = norm.cdf(d1)
    Nd2 = norm.cdf(d2)

    exp_rf = np.exp(-r_f * T)
    exp_rd = np.exp(-r_d * T)

    # Gamma and Vega are the same for calls and puts
    gamma = exp_rf * nd1 / (S * sigma * sqrt_T)
    vega_raw = S * exp_rf * nd1 * sqrt_T  # per 1 unit of sigma

    if option_type == 'call':
        delta = exp_rf * Nd1
        theta = (-(S * sigma * exp_rf * nd1) / (2 * sqrt_T)
                 + r_f * S * exp_rf * Nd1
                 - r_d * K * exp_rd * Nd2)
        rho_d = K * T * exp_rd * Nd2
        rho_f = -S * T * exp_rf * Nd1
    else:
        Nmd1 = norm.cdf(-d1)
        Nmd2 = norm.cdf(-d2)
        delta = -exp_rf * Nmd1
        theta = (-(S * sigma * exp_rf * nd1) / (2 * sqrt_T)
                 - r_f * S * exp_rf * Nmd1
                 + r_d * K * exp_rd * Nmd2)
        rho_d = -K * T * exp_rd * Nmd2
        rho_f = S * T * exp_rf * Nmd1

    return {
        'delta': float(delta),
        'gamma': float(gamma),
        'vega': float(vega_raw / 100),     # per 1% vol change
        'theta': float(theta / 365),        # per calendar day
        'rho_d': float(rho_d / 100),        # per 1% domestic rate change
        'rho_f': float(rho_f / 100),        # per 1% foreign rate change
    }


def implied_volatility(price_market, S, K, T, r_d, r_f, option_type='call',
                        tol=1e-8, max_iter=100):
    """
    Calculate implied volatility using Newton-Raphson with bisection fallback.

    Parameters:
        price_market: Observed market price per unit of foreign currency
        S, K, T, r_d, r_f: Option parameters (see gk_price)
        option_type: 'call' or 'put'
        tol: Convergence tolerance
        max_iter: Maximum Newton-Raphson iterations

    Returns:
        Implied volatility (annualized, as decimal e.g. 0.85 = 85%)
    """
    if T <= 0:
        raise ValueError("Cannot compute implied volatility at or past expiry")

    # Validate: price must be within arbitrage bounds
    if option_type == 'call':
        lower_bound = max(S * np.exp(-r_f * T) - K * np.exp(-r_d * T), 0)
        upper_bound = S * np.exp(-r_f * T)
    else:
        lower_bound = max(K * np.exp(-r_d * T) - S * np.exp(-r_f * T), 0)
        upper_bound = K * np.exp(-r_d * T)

    if price_market <= lower_bound:
        raise ValueError("Market price is below intrinsic value")
    if price_market >= upper_bound:
        raise ValueError("Market price exceeds arbitrage upper bound")

    # Initial guess: Brenner-Subrahmanyam approximation
    sigma = np.sqrt(2 * np.pi / T) * price_market / S
    sigma = np.clip(sigma, 0.01, 5.0)

    # Newton-Raphson
    for _ in range(max_iter):
        price_calc = gk_price(S, K, T, r_d, r_f, sigma, option_type)
        diff = price_calc - price_market

        if abs(diff) < tol:
            return float(sigma)

        sqrt_T = np.sqrt(T)
        d1 = (np.log(S / K) + (r_d - r_f + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
        vega = S * np.exp(-r_f * T) * norm.pdf(d1) * sqrt_T

        if vega < 1e-12:
            break

        sigma -= diff / vega
        sigma = np.clip(sigma, 0.001, 10.0)

    # Fallback: bisection method
    sigma_low, sigma_high = 0.001, 10.0
    for _ in range(200):
        sigma_mid = (sigma_low + sigma_high) / 2.0
        price_mid = gk_price(S, K, T, r_d, r_f, sigma_mid, option_type)

        if abs(price_mid - price_market) < tol:
            return float(sigma_mid)

        if price_mid > price_market:
            sigma_high = sigma_mid
        else:
            sigma_low = sigma_mid

    return float(sigma_mid)


def breakeven_spot(K, premium_per_unit, option_type='call'):
    """Calculate breakeven spot price at expiry."""
    if option_type == 'call':
        return K + premium_per_unit
    else:
        return K - premium_per_unit
