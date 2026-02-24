"""
Market data fetcher for OTC options calculator.

Tries multiple free data sources for spot prices, historical volatility,
and interest rates. Falls back gracefully to None when data is unavailable.
"""

import logging
import requests
import numpy as np
from datetime import datetime, date, timedelta
from scipy.stats import norm
from scipy.optimize import brentq


log = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
_TIMEOUT = 10

# Reusable Yahoo session (cookie + crumb for authenticated endpoints)
_yahoo_session = None
_yahoo_crumb = None

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
    GBP: Bank of England Bank Rate -> default.

    Returns: (float rate, str source) or (default, 'default')
    """
    defaults = {
        'EUR': 0.025,
        'USD': 0.045,
        'GBP': 0.04,
        'CHF': 0.005,
        'JPY': 0.005,
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

    if currency == 'GBP':
        rate = _boe_bank_rate()
        if rate is not None:
            return rate, 'BoE Bank Rate'

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


def _boe_bank_rate():
    """Fetch the current Bank of England Bank Rate from their statistical database."""
    try:
        url = ('https://www.bankofengland.co.uk/boeapps/database/'
               'fromshowcolumns.asp?csv.x=yes&SeriesCodes=IUDBEDR'
               '&UsingCodes=Y&CSVF=CN&VPD=Y&VFD=N')
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        log.info("BoE Bank Rate -> status %s", resp.status_code)
        if resp.status_code != 200:
            return None
        lines = resp.text.strip().split('\n')
        # Last data line contains the most recent rate (percentage value)
        for line in reversed(lines):
            parts = [p.strip().strip('"') for p in line.split(',')]
            if len(parts) >= 2:
                try:
                    rate = float(parts[-1])
                    if 0 <= rate <= 20:
                        return rate / 100.0
                except ValueError:
                    continue
    except Exception as e:
        log.warning("BoE Bank Rate fetch error: %s", e)
    return None


def _get_yahoo_session():
    """Get authenticated Yahoo Finance session with cookie + crumb."""
    global _yahoo_session, _yahoo_crumb
    if _yahoo_session is not None and _yahoo_crumb is not None:
        return _yahoo_session, _yahoo_crumb
    try:
        _yahoo_session = requests.Session()
        _yahoo_session.get('https://fc.yahoo.com', headers=_HEADERS,
                           timeout=_TIMEOUT, allow_redirects=True)
        resp = _yahoo_session.get(
            'https://query2.finance.yahoo.com/v1/test/getcrumb',
            headers=_HEADERS, timeout=_TIMEOUT)
        _yahoo_crumb = resp.text.strip()
        log.info("Yahoo crumb obtained: %s...", _yahoo_crumb[:6])
        return _yahoo_session, _yahoo_crumb
    except Exception as e:
        log.warning("Yahoo session init error: %s", e)
        _yahoo_session = None
        _yahoo_crumb = None
        return None, None


def _bs_call_price(S, K, T, r, sigma):
    """Plain Black-Scholes call price (no dividend/foreign rate)."""
    if T <= 0 or sigma <= 0:
        return max(S - K, 0.0)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return float(S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2))


def _bs_implied_vol(price, S, K, T, r):
    """Solve implied vol from a call price using Brent's method."""
    if T <= 0 or price <= 0:
        return None
    intrinsic = max(S - K * np.exp(-r * T), 0)
    if price <= intrinsic:
        return None
    try:
        iv = brentq(lambda s: _bs_call_price(S, K, T, r, s) - price,
                     0.01, 5.0, xtol=1e-6)
        return float(iv)
    except Exception:
        return None


def fetch_slv_implied_vol(target_T=1.0):
    """
    Fetch ATM implied volatility from SLV (iShares Silver Trust) options.

    Uses Yahoo Finance options chain, finds the expiry closest to target_T,
    picks ATM calls, and calculates IV from their last traded prices.

    Parameters:
        target_T: Target time to expiry in years (matches user's option tenor)

    Returns:
        (float iv, float slv_price, str expiry_used, str source) or (None, ...)
    """
    try:
        session, crumb = _get_yahoo_session()
        if session is None:
            return None, None, None, None

        # Get available expiry dates
        url = f'https://query2.finance.yahoo.com/v7/finance/options/SLV?crumb={crumb}'
        resp = session.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            log.warning("SLV options list -> HTTP %s", resp.status_code)
            return None, None, None, None

        data = resp.json()
        result = data.get('optionChain', {}).get('result', [])
        if not result:
            return None, None, None, None

        slv_price = result[0].get('quote', {}).get('regularMarketPrice')
        if not slv_price:
            return None, None, None, None

        expiry_timestamps = result[0].get('expirationDates', [])
        if not expiry_timestamps:
            return None, None, None, None

        # Find expiry closest to target_T
        today = date.today()
        target_date = today + timedelta(days=int(target_T * 365))
        best_ts = None
        best_diff = float('inf')
        for ts in expiry_timestamps:
            exp_date = datetime.fromtimestamp(ts).date()
            diff = abs((exp_date - target_date).days)
            if diff < best_diff:
                best_diff = diff
                best_ts = ts

        if best_ts is None:
            return None, None, None, None

        best_expiry = datetime.fromtimestamp(best_ts).date()
        T_actual = (best_expiry - today).days / 365.0
        if T_actual <= 0:
            return None, None, None, None

        # Fetch options chain for the selected expiry
        url2 = (f'https://query2.finance.yahoo.com/v7/finance/options/SLV'
                f'?crumb={crumb}&date={best_ts}')
        resp2 = session.get(url2, headers=_HEADERS, timeout=_TIMEOUT)
        if resp2.status_code != 200:
            log.warning("SLV options chain -> HTTP %s", resp2.status_code)
            return None, None, None, None

        data2 = resp2.json()
        options = data2['optionChain']['result'][0].get('options', [])
        if not options:
            return None, None, None, None

        calls = options[0].get('calls', [])
        if not calls:
            return None, None, None, None

        # Find ATM calls (within 5% of spot) with valid prices
        r_usd = 0.04  # approximate US risk-free rate
        atm_ivs = []
        for c in calls:
            strike = c.get('strike', 0)
            last = c.get('lastPrice', 0)
            if last <= 0.5:
                continue
            # Within 5% of ATM
            if abs(strike - slv_price) / slv_price > 0.05:
                continue
            iv = _bs_implied_vol(last, slv_price, strike, T_actual, r_usd)
            if iv and 0.05 < iv < 3.0:
                atm_ivs.append(iv)

        if not atm_ivs:
            return None, None, None, None

        # Use median to reduce outlier impact
        atm_iv = float(np.median(atm_ivs))
        source = (f'SLV options ({best_expiry.isoformat()}, '
                  f'{len(atm_ivs)} ATM strikes, T={T_actual:.2f}y)')

        log.info("SLV ATM IV: %.2f%% from %s", atm_iv * 100, source)
        return atm_iv, float(slv_price), best_expiry.isoformat(), source

    except Exception as e:
        log.warning("fetch_slv_implied_vol error: %s", e)
        return None, None, None, None


def fetch_all_market_data(base='XAG', quote='EUR', target_T=1.0):
    """
    Fetch all available market data for an option pair.

    Returns dict with keys: spot, historical_vol, rate_domestic, rate_foreign,
                            slv_iv, slv_price, slv_expiry, sources
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

    # SLV implied vol (only for silver)
    slv_iv = None
    slv_price = None
    slv_expiry = None
    slv_src = None
    if base == 'XAG':
        slv_iv, slv_price, slv_expiry, slv_src = fetch_slv_implied_vol(target_T)

    sources = {
        'spot': spot_src,
        'volatility': vol_src,
        'rate_domestic': rd_src,
        'rate_foreign': rf_src,
        'slv_iv': slv_src,
    }

    return {
        'spot': spot,
        'historical_vol': hist_vol,
        'rate_domestic': rate_domestic,
        'rate_foreign': rate_foreign,
        'slv_iv': slv_iv,
        'slv_price': slv_price,
        'slv_expiry': slv_expiry,
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
