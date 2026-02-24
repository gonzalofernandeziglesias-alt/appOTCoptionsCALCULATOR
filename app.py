"""
OTC Options Price Calculator — Flask Application

Provides a web interface for pricing European vanilla OTC options
using the Garman-Kohlhagen model. Supports FX pairs and precious metals.
"""

from flask import Flask, render_template, jsonify, request
from datetime import datetime, date
import logging
import time
import traceback

from pricing.black_scholes import gk_price, gk_greeks, implied_volatility, breakeven_spot
from market_data.fetcher import fetch_all_market_data

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(name)s %(levelname)s: %(message)s')

app = Flask(__name__)


_START_TS = str(int(time.time()))


@app.route('/')
def index():
    today = date.today().isoformat()
    return render_template('index.html', today=today, cache_bust=_START_TS)


@app.route('/api/calculate', methods=['POST'])
def calculate():
    """Calculate option price, Greeks, and analytics from input parameters."""
    try:
        data = request.get_json()

        S = float(data['spot'])
        K = float(data['strike'])
        sigma = float(data['volatility']) / 100.0  # convert from percentage
        r_d = float(data['rate_domestic']) / 100.0
        r_f = float(data['rate_foreign']) / 100.0
        notional = float(data['notional'])
        option_type = data.get('option_type', 'call').lower()

        # Time to expiry
        valuation_date = datetime.strptime(data['valuation_date'], '%Y-%m-%d').date()
        expiry_date = datetime.strptime(data['expiry_date'], '%Y-%m-%d').date()
        days_to_expiry = (expiry_date - valuation_date).days
        if days_to_expiry < 0:
            return jsonify({'error': 'Expiry date must be after valuation date'}), 400
        day_count = data.get('day_count', 'ACT/365')
        day_base = 360 if day_count == 'ACT/360' else 365
        T = days_to_expiry / day_base

        # Price per unit
        price_unit = gk_price(S, K, T, r_d, r_f, sigma, option_type)
        total_premium = price_unit * notional

        # Greeks (per unit)
        greeks = gk_greeks(S, K, T, r_d, r_f, sigma, option_type)

        # Greeks scaled by notional
        greeks_total = {
            'delta': greeks['delta'] * notional,
            'gamma': greeks['gamma'] * notional,
            'vega': greeks['vega'] * notional,
            'theta': greeks['theta'] * notional,
            'rho_d': greeks['rho_d'] * notional,
            'rho_f': greeks['rho_f'] * notional,
        }

        # Breakeven at expiry
        be_spot = breakeven_spot(K, price_unit, option_type)

        # Moneyness
        if option_type == 'call':
            moneyness_pct = (S - K) / K * 100
        else:
            moneyness_pct = (K - S) / K * 100
        if abs(moneyness_pct) < 1:
            moneyness_label = 'ATM'
        elif moneyness_pct > 0:
            moneyness_label = 'ITM'
        else:
            moneyness_label = 'OTM'

        # Comparison with market premium if provided
        comparison = None
        market_premium = data.get('market_premium')
        if market_premium and str(market_premium).strip():
            mp = float(market_premium)
            market_unit = mp / notional
            diff = mp - total_premium
            diff_pct = (diff / total_premium * 100) if total_premium > 0 else 0
            comparison = {
                'market_premium': mp,
                'market_unit_price': market_unit,
                'difference': diff,
                'difference_pct': diff_pct,
                'assessment': 'Overpriced' if diff > 0 else 'Underpriced' if diff < 0 else 'Fair',
            }

        result = {
            'price_per_unit': round(price_unit, 6),
            'total_premium': round(total_premium, 2),
            'days_to_expiry': days_to_expiry,
            'T': round(T, 6),
            'greeks_unit': {k: round(v, 8) for k, v in greeks.items()},
            'greeks_total': {k: round(v, 4) for k, v in greeks_total.items()},
            'breakeven_spot': round(be_spot, 4),
            'moneyness': moneyness_label,
            'moneyness_pct': round(moneyness_pct, 2),
            'd1': None,
            'd2': None,
        }

        # Add d1/d2 for display
        if T > 0 and sigma > 0:
            import numpy as np
            sqrt_T = np.sqrt(T)
            d1 = (np.log(S / K) + (r_d - r_f + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
            d2 = d1 - sigma * sqrt_T
            result['d1'] = round(float(d1), 6)
            result['d2'] = round(float(d2), 6)

        if comparison:
            result['comparison'] = comparison

        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Calculation error: {str(e)}'}), 500


@app.route('/api/implied-vol', methods=['POST'])
def calc_implied_vol():
    """Calculate implied volatility from a market premium."""
    try:
        data = request.get_json()

        S = float(data['spot'])
        K = float(data['strike'])
        r_d = float(data['rate_domestic']) / 100.0
        r_f = float(data['rate_foreign']) / 100.0
        notional = float(data['notional'])
        option_type = data.get('option_type', 'call').lower()

        valuation_date = datetime.strptime(data['valuation_date'], '%Y-%m-%d').date()
        expiry_date = datetime.strptime(data['expiry_date'], '%Y-%m-%d').date()
        days_to_expiry = (expiry_date - valuation_date).days
        day_count = data.get('day_count', 'ACT/365')
        day_base = 360 if day_count == 'ACT/360' else 365
        T = days_to_expiry / day_base

        market_premium = float(data['market_premium'])
        price_market = market_premium / notional  # price per unit

        iv = implied_volatility(price_market, S, K, T, r_d, r_f, option_type)

        return jsonify({
            'implied_volatility': round(iv * 100, 4),  # as percentage
            'price_per_unit_market': round(price_market, 6),
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Implied vol calculation error: {str(e)}'}), 500


@app.route('/api/market-data', methods=['POST'])
def market_data():
    """Fetch live market data for a currency pair."""
    try:
        data = request.get_json()
        base = data.get('base', 'XAG')
        quote = data.get('quote', 'EUR')

        # Compute target_T from valuation/expiry dates if provided
        target_T = 1.0
        val_str = data.get('valuation_date')
        exp_str = data.get('expiry_date')
        if val_str and exp_str:
            try:
                val_date = datetime.strptime(val_str, '%Y-%m-%d').date()
                exp_date = datetime.strptime(exp_str, '%Y-%m-%d').date()
                days = (exp_date - val_date).days
                if days > 0:
                    target_T = days / 365.0
            except ValueError:
                pass

        result = fetch_all_market_data(base, quote, target_T=target_T)

        # Convert vol to percentage for display
        if result.get('historical_vol') is not None:
            result['historical_vol'] = round(result['historical_vol'] * 100, 2)
        if result.get('rate_domestic') is not None:
            result['rate_domestic'] = round(result['rate_domestic'] * 100, 4)
        if result.get('rate_foreign') is not None:
            result['rate_foreign'] = round(result['rate_foreign'] * 100, 4)
        if result.get('slv_iv') is not None:
            result['slv_iv'] = round(result['slv_iv'] * 100, 2)

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'Market data fetch error: {str(e)}'}), 500


@app.route('/api/debug')
def debug_info():
    """Quick check that the server is running the latest code."""
    return jsonify({
        'version': 'v3-cache-bust',
        'started': _START_TS,
        'today': date.today().isoformat(),
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
