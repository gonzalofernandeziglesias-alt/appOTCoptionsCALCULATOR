"""
Market data fetcher for OTC options calculator.

Tries multiple free data sources for spot prices, historical volatility,
and interest rates. Falls back gracefully to None when data is unavailable.
"""

import logging
import requests
import numpy as np
from datetime import datetime, timedelta


log = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
_TIMEOUT = 10

# Yahoo Finance FX tickers (XAG=X etc.) are dead for metals.
# Futures tickers are the only reliable free source.
_METAL_FUTURES = {
    'XAG': 'SI=F',
    'XAU': 'GC=F',
    'XPT': 'PL=F',
    'XPD': 'PA=F',
}


def fetch_spot(base='XAG', quote='EUR'):
    """
    Fetch current spot price for a currency/metal pair.
    For metals: uses futures (SI=F) / FX rate as cross.

    Returns: (float spot, str source_description) or (None, None)
    """
    if base in _METAL_FUTURES:
        # Metals: get USD price from futures, then cross via FX
        ticker = _METAL_FUTURES[base]
        metal_usd = _yahoo_quote(ticker)
        if metal_usd is None:
            log.warning("fetch_spot: Yahoo %s returned None", ticker)
            return None, None

        if quote == 'USD':
            return round(metal_usd, 6), f'{ticker}'

        fx_ticker = f'{quote}USD=X'
        quote_usd = _yahoo_quote(fx_ticker)
        if quote_usd and quote_usd != 0:
            spot = round(metal_usd / quote_usd, 6)
            return spot, f'{ticker} / {fx_ticker}'

        log.warning("fetch_spot: Yahoo %s returned %s", fx_ticker, quote_usd)
        return None, None

    # Direct FX pair
    ticker = f'{base}{quote}=X'
    direct = _yahoo_quote(ticker)
    if direct:
        return round(direct, 6), ticker

    # Try inverse
    inv_ticker = f'{quote}{base}=X'
    inverse = _yahoo_quote(inv_ticker)
    if inverse and inverse != 0:
        return round(1.0 / inverse, 6), f'1 / {inv_ticker}'

    return None, None


def fetch_historical_volatility(base='XAG', quote='EUR'):
    """
    Compute annualized historical volatility from daily close prices.
    Uses log-return standard deviation * sqrt(252).
    Filters outlier returns (>10% daily) to remove futures rollover noise.

    Returns: (float annualized_vol, str source) or (None, None)
    """
    try:
        # For metals, go straight to futures (FX tickers are dead)
        if base in _METAL_FUTURES:
            symbol = _METAL_FUTURES[base]
        else:
            symbol = f'{base}{quote}=X'

        closes = _yahoo_history(symbol, period='3mo')
        if closes is None or len(closes) < 15:
            log.warning("fetch_historical_volatility: %s returned %s points",
                        symbol, len(closes) if closes else 0)
            return None, None

        log_returns = np.diff(np.log(np.array(closes)))

        # Filter out futures rollover spikes (>10% daily move)
        mask = np.abs(log_returns) < 0.10
        filtered = log_returns[mask]
        n_filtered = len(log_returns) - len(filtered)

        if len(filtered) < 10:
            log.warning("fetch_historical_volatility: too few points after filtering")
            return None, None

        vol = float(np.std(filtered, ddof=1) * np.sqrt(252))
        source = f'{symbol} (3mo, {len(filtered)}pts'
        if n_filtered > 0:
            source += f', {n_filtered} outliers removed'
        source += ')'
        return round(vol, 4), source
    except Exception as e:
        log.warning("fetch_historical_volatility error: %s", e)
        return None, None


def fetch_risk_free_rate(currency='EUR'):
    """
    Fetch risk-free rate for a currency.
    EUR: ECB €STR -> ECB deposit facility rate -> default.
    USD: Yahoo ^IRX (13-week T-bill) -> default.

    Returns: (float rate, str source) or (default, 'default')
    """
    defaults = {
        'EUR': 0.025,
        'USD': 0.045,
        'GBP': 0.04,
        'CHF': 0.01,
        'JPY': 0.001,
    }

    if currency == 'EUR':
        # Source 1: ECB €STR (Euro Short-Term Rate) — updated daily
        rate = _ecb_csv_rate(
            'https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT'
            '?lastNObservations=1&format=csvdata')
        if rate is not None:
            return rate, 'ECB €STR'
        # Source 2: ECB deposit facility rate
        rate = _ecb_csv_rate(
            'https://data-api.ecb.europa.eu/service/data/FM/B.U2.EUR.4F.KR.DFR.LEV'
            '?lastNObservations=1&format=csvdata')
        if rate is not None:
            return rate, 'ECB DFR'

    if currency == 'USD':
        irx = _yahoo_quote('^IRX')
        if irx is not None:
            rate = irx / 100.0
            if 0 <= rate <= 0.20:
                return rate, 'Yahoo ^IRX'

    default = defaults.get(currency)
    return default, 'default'


def _ecb_csv_rate(url):
    """Parse an ECB CSV data response and return the rate as a decimal."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        log.info("ECB %s -> status %s", url.split('/')[-1].split('?')[0], resp.status_code)
        if resp.status_code == 200:
            lines = resp.text.strip().split('\n')
            if len(lines) >= 2:
                header = lines[0].split(',')
                data = lines[-1].split(',')
                obs_idx = header.index('OBS_VALUE') if 'OBS_VALUE' in header else -1
                if obs_idx < 0:
                    log.warning("ECB CSV: OBS_VALUE column not found in: %s", header)
                    return None
                value = data[obs_idx].strip()
                log.info("ECB CSV OBS_VALUE = %s", value)
                rate = float(value) / 100.0
                if 0 <= rate <= 0.20:
                    return rate
                log.warning("ECB rate %s out of range", rate)
    except Exception as e:
        log.warning("ECB fetch error: %s", e)
    return None


def fetch_all_market_data(base='XAG', quote='EUR'):
    """
    Fetch all available market data for an option pair.

    Returns dict with keys: spot, historical_vol, rate_domestic, rate_foreign, sources
    Values are None where data is unavailable.
    """
    spot, spot_src = fetch_spot(base, quote)
    hist_vol, vol_src = fetch_historical_volatility(base, quote)
    rate_domestic, rd_src = fetch_risk_free_rate(quote)

    # Foreign rate for precious metals is the lease rate (not freely available)
    metal_lease_rates = {
        'XAG': 0.005,   # Silver: ~0.5%
        'XAU': 0.002,   # Gold: ~0.2%
        'XPT': 0.005,   # Platinum
        'XPD': 0.005,   # Palladium
    }
    if base in metal_lease_rates:
        rate_foreign = metal_lease_rates[base]
        rf_src = 'lease rate estimate'
    else:
        rate_foreign, rf_src = fetch_risk_free_rate(base)

    sources = {
        'spot': spot_src,
        'volatility': vol_src,
        'rate_domestic': rd_src,
        'rate_foreign': rf_src,
    }

    return {
        'spot': spot,
        'historical_vol': hist_vol,
        'rate_domestic': rate_domestic,
        'rate_foreign': rate_foreign,
        'sources': sources,
    }


def _yahoo_quote(symbol):
    """Fetch latest quote from Yahoo Finance v8 chart API."""
    try:
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
        params = {'range': '1d', 'interval': '1d'}
        resp = requests.get(url, headers=_HEADERS, params=params, timeout=_TIMEOUT)
        if resp.status_code != 200:
            log.warning("Yahoo quote %s -> HTTP %s", symbol, resp.status_code)
            return None
        data = resp.json()
        result = data.get('chart', {}).get('result')
        if result and len(result) > 0:
            price = result[0]['meta'].get('regularMarketPrice')
            log.info("Yahoo %s = %s", symbol, price)
            return price
    except Exception as e:
        log.warning("Yahoo quote %s error: %s", symbol, e)
    return None


def _yahoo_history(symbol, period='3mo'):
    """Fetch historical daily close prices from Yahoo Finance."""
    try:
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
        params = {'range': period, 'interval': '1d'}
        resp = requests.get(url, headers=_HEADERS, params=params, timeout=_TIMEOUT)
        if resp.status_code != 200:
            log.warning("Yahoo history %s -> HTTP %s", symbol, resp.status_code)
            return None
        data = resp.json()
        result = data.get('chart', {}).get('result')
        if result and len(result) > 0:
            closes = result[0]['indicators']['quote'][0].get('close', [])
            valid = [c for c in closes if c is not None]
            log.info("Yahoo history %s: %d points", symbol, len(valid))
            return valid
    except Exception as e:
        log.warning("Yahoo history %s error: %s", symbol, e)
    return None
