"""
Market data fetcher for OTC options calculator.

Tries multiple free data sources for spot prices, historical volatility,
and interest rates. Falls back gracefully to None when data is unavailable.
"""

import requests
import numpy as np
from datetime import datetime, timedelta


_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
_TIMEOUT = 10

# Yahoo Finance FX tickers (XAG=X etc.) are unreliable for metals.
# Futures tickers work as a more stable alternative for spot approximation.
_METAL_FUTURES = {
    'XAG': 'SI=F',
    'XAU': 'GC=F',
    'XPT': 'PL=F',
    'XPD': 'PA=F',
}


def fetch_spot(base='XAG', quote='EUR'):
    """
    Fetch current spot price for a currency/metal pair.
    Tries Yahoo Finance, falls back to ECB + metal cross rate.

    Returns: float spot price or None
    """
    # For metal pairs, compute cross: e.g. XAG/EUR = XAG/USD / EUR/USD
    if base in ('XAG', 'XAU', 'XPT', 'XPD'):
        metal_usd = _yahoo_quote(f'{base}USD=X')
        if metal_usd is None:
            metal_usd = _yahoo_quote(_METAL_FUTURES.get(base, f'{base}=F'))

        if quote == 'USD':
            return metal_usd

        quote_usd = _yahoo_quote(f'{quote}USD=X')
        if metal_usd and quote_usd and quote_usd != 0:
            return round(metal_usd / quote_usd, 6)
        return None

    # Direct FX pair
    direct = _yahoo_quote(f'{base}{quote}=X')
    if direct:
        return round(direct, 6)

    # Try inverse
    inverse = _yahoo_quote(f'{quote}{base}=X')
    if inverse and inverse != 0:
        return round(1.0 / inverse, 6)

    return None


def fetch_historical_volatility(base='XAG', quote='EUR', days=60):
    """
    Compute annualized historical volatility from daily close prices.
    Uses log-return standard deviation * sqrt(252).

    Returns: float annualized vol or None
    """
    try:
        if base in ('XAG', 'XAU', 'XPT', 'XPD'):
            symbol = f'{base}USD=X'
        else:
            symbol = f'{base}{quote}=X'

        closes = _yahoo_history(symbol, period='3mo')

        # Fallback to futures ticker if FX ticker has no data
        if (closes is None or len(closes) < 15) and base in _METAL_FUTURES:
            closes = _yahoo_history(_METAL_FUTURES[base], period='3mo')
        if closes is None or len(closes) < 15:
            return None

        log_returns = np.diff(np.log(closes))
        vol = float(np.std(log_returns, ddof=1) * np.sqrt(252))
        return round(vol, 4)
    except Exception:
        return None


def fetch_risk_free_rate(currency='EUR'):
    """
    Fetch approximate risk-free rate for a currency.
    Uses ECB data for EUR, falls back to reasonable defaults.

    Returns: float annual rate (e.g. 0.025 for 2.5%) or None
    """
    defaults = {
        'EUR': 0.025,
        'USD': 0.045,
        'GBP': 0.04,
        'CHF': 0.01,
        'JPY': 0.001,
    }

    # Try ECB for EUR
    if currency == 'EUR':
        try:
            url = ('https://data-api.ecb.europa.eu/service/data/FM/B.U2.EUR.4F.KR.DFR.LEV'
                   '?lastNObservations=1&format=csvdata')
            resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            if resp.status_code == 200:
                lines = resp.text.strip().split('\n')
                if len(lines) >= 2:
                    header = lines[0].split(',')
                    data = lines[-1].split(',')
                    obs_idx = header.index('OBS_VALUE') if 'OBS_VALUE' in header else -1
                    value = data[obs_idx].strip() if obs_idx >= 0 else data[-1].strip()
                    rate = float(value) / 100.0
                    if 0 <= rate <= 0.20:
                        return rate
        except Exception:
            pass

    return defaults.get(currency)


def fetch_all_market_data(base='XAG', quote='EUR'):
    """
    Fetch all available market data for an option pair.

    Returns dict with keys: spot, historical_vol, rate_domestic, rate_foreign
    Values are None where data is unavailable.
    """
    spot = fetch_spot(base, quote)
    hist_vol = fetch_historical_volatility(base, quote)
    rate_domestic = fetch_risk_free_rate(quote)

    # Foreign rate for precious metals is the lease rate
    # These are not freely available; use reasonable defaults
    metal_lease_rates = {
        'XAG': 0.005,   # Silver: ~0.5%
        'XAU': 0.002,   # Gold: ~0.2%
        'XPT': 0.005,   # Platinum
        'XPD': 0.005,   # Palladium
    }
    rate_foreign = metal_lease_rates.get(base, fetch_risk_free_rate(base))

    return {
        'spot': spot,
        'historical_vol': hist_vol,
        'rate_domestic': rate_domestic,
        'rate_foreign': rate_foreign,
    }


def _yahoo_quote(symbol):
    """Fetch latest quote from Yahoo Finance v8 chart API."""
    try:
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
        params = {'range': '1d', 'interval': '1d'}
        resp = requests.get(url, headers=_HEADERS, params=params, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        data = resp.json()
        result = data.get('chart', {}).get('result')
        if result and len(result) > 0:
            return result[0]['meta'].get('regularMarketPrice')
    except Exception:
        pass
    return None


def _yahoo_history(symbol, period='3mo'):
    """Fetch historical daily close prices from Yahoo Finance."""
    try:
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
        params = {'range': period, 'interval': '1d'}
        resp = requests.get(url, headers=_HEADERS, params=params, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        data = resp.json()
        result = data.get('chart', {}).get('result')
        if result and len(result) > 0:
            closes = result[0]['indicators']['quote'][0].get('close', [])
            return [c for c in closes if c is not None]
    except Exception:
        pass
    return None
