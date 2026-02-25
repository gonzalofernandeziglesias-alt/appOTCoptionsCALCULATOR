/**
 * OTC Options Calculator — Frontend Logic
 */

document.addEventListener('DOMContentLoaded', function () {

    // DOM elements
    const els = {
        baseCurrency: document.getElementById('baseCurrency'),
        quoteCurrency: document.getElementById('quoteCurrency'),
        optionType: document.getElementById('optionType'),
        position: document.getElementById('position'),
        strike: document.getElementById('strike'),
        notional: document.getElementById('notional'),
        valuationDate: document.getElementById('valuationDate'),
        expiryDate: document.getElementById('expiryDate'),
        daysToExpiry: document.getElementById('daysToExpiry'),
        spot: document.getElementById('spot'),
        volatility: document.getElementById('volatility'),
        rateDomestic: document.getElementById('rateDomestic'),
        rateForeign: document.getElementById('rateForeign'),
        marketPremium: document.getElementById('marketPremium'),
        transactionFee: document.getElementById('transactionFee'),
        btnCalculate: document.getElementById('btnCalculate'),
        btnFetch: document.getElementById('btnFetch'),
        btnImpliedVol: document.getElementById('btnImpliedVol'),
        slvIvSection: document.getElementById('slvIvSection'),
        slvIv: document.getElementById('slvIv'),
        otcSpread: document.getElementById('otcSpread'),
        estOtcVol: document.getElementById('estOtcVol'),
        btnUseEstVol: document.getElementById('btnUseEstVol'),
        slvIvSource: document.getElementById('slvIvSource'),
        spotDays: document.getElementById('spotDays'),
        dayCount: document.getElementById('dayCount'),
        greeksTotal: document.getElementById('greeksTotal'),
        resultsSection: document.getElementById('resultsSection'),
        calcError: document.getElementById('calcError'),
        fetchStatus: document.getElementById('fetchStatus'),
        impliedVolResult: document.getElementById('impliedVolResult'),
    };

    // --- Utility ---
    function fmt(n, decimals) {
        if (n === null || n === undefined || isNaN(n)) return '—';
        return Number(n).toLocaleString('en-US', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }

    function fmtSigned(n, decimals) {
        if (n === null || n === undefined || isNaN(n)) return '—';
        const prefix = n >= 0 ? '+' : '';
        return prefix + fmt(n, decimals);
    }

    // --- Update days to expiry when dates change ---
    function addBusinessDays(startDate, n) {
        const d = new Date(startDate);
        for (let i = 0; i < n; i++) {
            d.setDate(d.getDate() + 1);
            while (d.getDay() === 0 || d.getDay() === 6) {
                d.setDate(d.getDate() + 1);
            }
        }
        return d;
    }

    function updateDaysToExpiry() {
        const val = els.valuationDate.value;
        const exp = els.expiryDate.value;
        if (val && exp) {
            const spotOffset = parseInt(els.spotDays.value) || 0;
            const valDate = new Date(val + 'T00:00:00');
            const spotDate = addBusinessDays(valDate, spotOffset);
            const expDate = new Date(exp + 'T00:00:00');
            const days = Math.round((expDate - spotDate) / (1000 * 60 * 60 * 24));
            els.daysToExpiry.value = days;
        }
    }

    els.valuationDate.addEventListener('change', updateDaysToExpiry);
    els.expiryDate.addEventListener('change', updateDaysToExpiry);
    els.spotDays.addEventListener('change', updateDaysToExpiry);
    els.dayCount.addEventListener('change', updateDaysToExpiry);

    // --- SLV IV + OTC Spread ---
    function updateEstOtcVol() {
        const slvIv = parseFloat(els.slvIv.value);
        const spread = parseFloat(els.otcSpread.value);
        if (!isNaN(slvIv) && !isNaN(spread)) {
            els.estOtcVol.value = (slvIv + spread).toFixed(2);
        }
    }

    els.otcSpread.addEventListener('input', updateEstOtcVol);

    els.btnUseEstVol.addEventListener('click', function () {
        const est = parseFloat(els.estOtcVol.value);
        if (!isNaN(est) && est > 0) {
            els.volatility.value = est.toFixed(2);
            showFetchStatus('success', 'Volatility set to ' + est.toFixed(2) + '% (SLV IV + OTC spread)');
        }
    });

    // --- Update labels when currencies change ---
    function updateLabels() {
        const base = els.baseCurrency.value;
        const quote = els.quoteCurrency.value;
        document.getElementById('strikeUnit').textContent = quote;
        document.getElementById('notionalUnit').textContent = base;
        document.getElementById('spotUnit').textContent = quote + '/' + base;
        document.getElementById('rateLabel_d').textContent = quote;
        document.getElementById('rateLabel_f').textContent = base;
        updateSummary();
    }

    function updateSummary() {
        const base = els.baseCurrency.value;
        const quote = els.quoteCurrency.value;
        const type = els.optionType.value;
        const pos = els.position.value;
        const strike = els.strike.value;
        const notional = els.notional.value;
        const expiry = els.expiryDate.value;

        const typeLabel = type === 'call'
            ? `${base} Call / ${quote} Put`
            : `${base} Put / ${quote} Call`;
        const posLabel = pos === 'buy' ? 'Buy' : 'Sell';
        const actionLabel = type === 'call' ? 'purchase' : 'sell';
        const face = (parseFloat(strike) * parseFloat(notional)).toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });

        const expiryFmt = expiry ? new Date(expiry + 'T00:00:00').toLocaleDateString('en-US', {
            day: 'numeric', month: 'short', year: 'numeric'
        }) : '—';

        document.getElementById('optionSummary').innerHTML =
            `<strong>${typeLabel}</strong> &mdash; European Vanilla<br>` +
            `${posLabel} the right to ${actionLabel} <strong>${fmt(parseFloat(notional), 0)} ${base}</strong> ` +
            `at <strong>${fmt(parseFloat(strike), 4)} ${quote}</strong> per ${base}<br>` +
            `Face amount: <strong>${face} ${quote}</strong><br>` +
            `Expiry: <strong>${expiryFmt}</strong>`;
    }

    els.baseCurrency.addEventListener('change', updateLabels);
    els.quoteCurrency.addEventListener('change', updateLabels);
    els.optionType.addEventListener('change', updateSummary);
    els.position.addEventListener('change', updateSummary);
    els.strike.addEventListener('input', updateSummary);
    els.notional.addEventListener('input', updateSummary);
    els.expiryDate.addEventListener('change', updateSummary);

    // --- Calculate ---
    els.btnCalculate.addEventListener('click', doCalculate);

    // Store last result for greeks toggle
    let lastResult = null;

    async function doCalculate() {
        els.calcError.style.display = 'none';
        els.btnCalculate.disabled = true;
        document.getElementById('calcSpinner').style.display = 'inline-block';

        const payload = {
            spot: parseFloat(els.spot.value),
            strike: parseFloat(els.strike.value),
            volatility: parseFloat(els.volatility.value),
            rate_domestic: parseFloat(els.rateDomestic.value),
            rate_foreign: parseFloat(els.rateForeign.value),
            notional: parseFloat(els.notional.value),
            option_type: els.optionType.value,
            valuation_date: els.valuationDate.value,
            expiry_date: els.expiryDate.value,
            spot_days: parseInt(els.spotDays.value) || 0,
            day_count: els.dayCount.value,
            market_premium: els.marketPremium.value || null,
        };

        try {
            const resp = await fetch('/api/calculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await resp.json();

            if (!resp.ok) {
                throw new Error(data.error || 'Calculation failed');
            }

            lastResult = data;
            displayResults(data);

        } catch (err) {
            els.calcError.textContent = err.message;
            els.calcError.style.display = 'block';
            els.resultsSection.classList.remove('visible');
        } finally {
            els.btnCalculate.disabled = false;
            document.getElementById('calcSpinner').style.display = 'none';
        }
    }

    function displayResults(data) {
        const quote = els.quoteCurrency.value;
        const base = els.baseCurrency.value;
        const position = els.position.value;
        const sign = position === 'buy' ? 1 : -1;

        // Price
        document.getElementById('resPriceUnit').textContent = fmt(data.price_per_unit, 4);
        document.getElementById('resPriceUnitLabel').textContent = `${quote} per ${base}`;
        document.getElementById('resTotalPremium').textContent = fmt(data.total_premium, 2);
        document.getElementById('resTotalPremiumLabel').textContent = quote;

        // Moneyness
        const mEl = document.getElementById('resMoneyness');
        mEl.textContent = data.moneyness;
        mEl.className = 'badge badge-' + data.moneyness.toLowerCase();
        document.getElementById('resMoneynessVal').textContent = ` (${fmtSigned(data.moneyness_pct, 1)}%)`;

        // Breakeven
        document.getElementById('resBreakeven').textContent = fmt(data.breakeven_spot, 4) + ' ' + quote;

        // Model details
        document.getElementById('resT').textContent = fmt(data.T, 6);
        document.getElementById('resD1').textContent = data.d1 !== null ? fmt(data.d1, 6) : '—';
        document.getElementById('resD2').textContent = data.d2 !== null ? fmt(data.d2, 6) : '—';
        if (data.d1 !== null) {
            // Approximate N(d) using error function
            document.getElementById('resNd1').textContent = fmt(normalCDF(data.d1), 6);
            document.getElementById('resNd2').textContent = fmt(normalCDF(data.d2), 6);
        }

        // Greeks
        updateGreeksDisplay(data);

        // Position P&L
        const pnlResult = document.getElementById('pnlResult');
        const pnlEmpty = document.getElementById('pnlEmpty');
        const entryPremium = parseFloat(els.marketPremium.value);

        if (!isNaN(entryPremium) && entryPremium > 0) {
            pnlEmpty.style.display = 'none';
            pnlResult.style.display = 'block';

            const currentValue = data.total_premium;
            // Buy: P&L = current value - entry cost
            // Sell: P&L = entry revenue - current liability
            const pnl = sign * (currentValue - entryPremium);
            const pnlPct = (pnl / entryPremium) * 100;

            document.getElementById('pnlEntry').textContent = fmt(entryPremium, 2);
            document.getElementById('pnlMtM').textContent = fmt(currentValue, 2);

            const pnlAmountEl = document.getElementById('pnlAmount');
            pnlAmountEl.textContent = `${fmtSigned(pnl, 2)} ${quote}`;
            pnlAmountEl.className = pnl >= 0 ? 'pnl-profit' : 'pnl-loss';

            const pnlPctEl = document.getElementById('pnlPercent');
            pnlPctEl.textContent = `(${fmtSigned(pnlPct, 1)}%)`;
            pnlPctEl.className = pnl >= 0 ? 'pnl-profit' : 'pnl-loss';

            // Intrinsic and time value decomposition
            const spotVal = parseFloat(els.spot.value);
            const strikeVal = parseFloat(els.strike.value);
            const notionalVal = parseFloat(els.notional.value);
            let intrinsic;
            if (els.optionType.value === 'call') {
                intrinsic = Math.max(spotVal - strikeVal, 0) * notionalVal;
            } else {
                intrinsic = Math.max(strikeVal - spotVal, 0) * notionalVal;
            }
            const timeValue = currentValue - intrinsic;

            document.getElementById('pnlIntrinsic').textContent = fmt(intrinsic, 2) + ' ' + quote;
            document.getElementById('pnlTimeValue').textContent = fmt(timeValue, 2) + ' ' + quote;
        } else {
            pnlEmpty.style.display = 'block';
            pnlResult.style.display = 'none';
        }

        els.resultsSection.classList.add('visible');
    }

    function updateGreeksDisplay(data) {
        if (!data) return;
        const isTotal = els.greeksTotal.checked;
        const g = isTotal ? data.greeks_total : data.greeks_unit;
        const dec = isTotal ? 2 : 6;

        document.getElementById('gDelta').textContent = fmt(g.delta, dec);
        document.getElementById('gGamma').textContent = fmt(g.gamma, isTotal ? 4 : 8);
        document.getElementById('gVega').textContent = fmt(g.vega, dec);
        document.getElementById('gTheta').textContent = fmt(g.theta, dec);
        document.getElementById('gRhoD').textContent = fmt(g.rho_d, dec);
        document.getElementById('gRhoF').textContent = fmt(g.rho_f, dec);

        // Delta interpretation
        const deltaDesc = document.getElementById('gDeltaDesc');
        if (isTotal) {
            const equiv = Math.abs(g.delta);
            deltaDesc.textContent = `Equiv. ${fmt(equiv, 0)} ${els.baseCurrency.value} spot`;
        } else {
            deltaDesc.textContent = 'Spot sensitivity';
        }
    }

    els.greeksTotal.addEventListener('change', function () {
        if (lastResult) updateGreeksDisplay(lastResult);
    });

    // --- Fetch Market Data ---
    els.btnFetch.addEventListener('click', async function () {
        els.btnFetch.disabled = true;
        document.getElementById('fetchSpinner').style.display = 'inline-block';
        els.fetchStatus.style.display = 'none';

        try {
            const resp = await fetch('/api/market-data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    base: els.baseCurrency.value,
                    quote: els.quoteCurrency.value,
                    valuation_date: els.valuationDate.value,
                    expiry_date: els.expiryDate.value,
                }),
            });
            const data = await resp.json();

            if (!resp.ok) {
                throw new Error(data.error || 'Fetch failed');
            }

            const sources = data.sources || {};
            let updated = [];
            if (data.spot != null) {
                els.spot.value = data.spot;
                updated.push('Spot: ' + data.spot + (sources.spot ? ' [' + sources.spot + ']' : ''));
            }
            if (data.rate_domestic != null) {
                els.rateDomestic.value = data.rate_domestic;
                updated.push('Dom: ' + data.rate_domestic + '%' + (sources.rate_domestic ? ' [' + sources.rate_domestic + ']' : ''));
            }
            if (data.rate_foreign != null) {
                els.rateForeign.value = data.rate_foreign;
                updated.push('For: ' + data.rate_foreign + '%' + (sources.rate_foreign ? ' [' + sources.rate_foreign + ']' : ''));
            }

            // SLV IV + OTC Spread (show as reference, don't auto-set volatility)
            if (data.slv_iv != null) {
                els.slvIv.value = data.slv_iv;
                els.otcSpread.value = 6.76;
                updateEstOtcVol();
                els.slvIvSection.style.display = 'block';

                const estVol = parseFloat(els.estOtcVol.value);
                if (!isNaN(estVol) && estVol > 0) {
                    updated.push('SLV IV: ' + data.slv_iv + '% (use panel below to apply)');
                }

                let srcDetail = sources.slv_iv || '';
                if (data.slv_price != null) {
                    srcDetail = 'SLV $' + data.slv_price.toFixed(2) + ' | ' + srcDetail;
                }
                els.slvIvSource.textContent = srcDetail;
            } else {
                // Fallback to historical vol
                if (data.historical_vol != null) {
                    els.volatility.value = data.historical_vol;
                    updated.push('Vol: ' + data.historical_vol + '% [hist]');
                }
                els.slvIvSection.style.display = 'none';
            }

            if (updated.length > 0) {
                showFetchStatus('success', updated.join(' | '));
            } else {
                showFetchStatus('info', 'No live data available. Please enter values manually.');
            }

        } catch (err) {
            showFetchStatus('error', 'Fetch failed: ' + err.message + '. Enter values manually.');
        } finally {
            els.btnFetch.disabled = false;
            document.getElementById('fetchSpinner').style.display = 'none';
        }
    });

    function showFetchStatus(type, msg) {
        els.fetchStatus.className = 'status-msg ' + type;
        els.fetchStatus.textContent = msg;
        els.fetchStatus.style.display = 'block';
    }

    // --- Implied Volatility ---
    els.btnImpliedVol.addEventListener('click', async function () {
        const mp = parseFloat(els.marketPremium.value);
        if (!mp || mp <= 0) {
            showImpliedVol('error', 'Enter a valid market premium first.');
            return;
        }

        els.btnImpliedVol.disabled = true;

        try {
            const resp = await fetch('/api/implied-vol', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    spot: parseFloat(els.spot.value),
                    strike: parseFloat(els.strike.value),
                    rate_domestic: parseFloat(els.rateDomestic.value),
                    rate_foreign: parseFloat(els.rateForeign.value),
                    notional: parseFloat(els.notional.value),
                    option_type: els.optionType.value,
                    valuation_date: els.valuationDate.value,
                    expiry_date: els.expiryDate.value,
                    spot_days: parseInt(els.spotDays.value) || 0,
                    day_count: els.dayCount.value,
                    market_premium: mp,
                }),
            });
            const data = await resp.json();

            if (!resp.ok) {
                throw new Error(data.error || 'Calculation failed');
            }

            const iv = data.implied_volatility;
            showImpliedVol('success',
                `Implied Volatility: ${fmt(iv, 2)}% ` +
                `(Premium per unit: ${fmt(data.price_per_unit_market, 4)})`
            );

            // Offer to use this vol
            const useBtn = document.createElement('button');
            useBtn.className = 'btn btn-sm btn-outline-success ms-2';
            useBtn.textContent = 'Use this vol';
            useBtn.onclick = function () {
                els.volatility.value = iv.toFixed(2);
                showImpliedVol('info', `Volatility set to ${fmt(iv, 2)}%`);
            };
            els.impliedVolResult.appendChild(useBtn);

            // Auto-calibrate OTC spread if SLV IV is available
            const slvIvVal = parseFloat(els.slvIv.value);
            if (!isNaN(slvIvVal) && slvIvVal > 0) {
                const impliedSpread = iv - slvIvVal;
                const calibrateBtn = document.createElement('button');
                calibrateBtn.className = 'btn btn-sm btn-outline-warning ms-2';
                calibrateBtn.textContent = `Set spread to ${fmt(impliedSpread, 1)}pp`;
                calibrateBtn.title = `Bank IV ${fmt(iv, 2)}% − SLV IV ${fmt(slvIvVal, 2)}% = ${fmt(impliedSpread, 1)}pp`;
                calibrateBtn.onclick = function () {
                    els.otcSpread.value = impliedSpread.toFixed(2);
                    updateEstOtcVol();
                    els.volatility.value = parseFloat(els.estOtcVol.value).toFixed(2);
                    showImpliedVol('info',
                        `OTC Spread calibrated: ${fmt(impliedSpread, 1)}pp (SLV ${fmt(slvIvVal, 2)}% + ${fmt(impliedSpread, 1)}pp = ${fmt(iv, 2)}%)`
                    );
                };
                els.impliedVolResult.appendChild(calibrateBtn);
            }

        } catch (err) {
            showImpliedVol('error', 'Error: ' + err.message);
        } finally {
            els.btnImpliedVol.disabled = false;
        }
    });

    function showImpliedVol(type, msg) {
        els.impliedVolResult.className = 'status-msg ' + type;
        els.impliedVolResult.textContent = msg;
        els.impliedVolResult.style.display = 'block';
    }

    // --- Normal CDF approximation for display ---
    function normalCDF(x) {
        const a1 = 0.254829592;
        const a2 = -0.284496736;
        const a3 = 1.421413741;
        const a4 = -1.453152027;
        const a5 = 1.061405429;
        const p = 0.3275911;
        const sign = x < 0 ? -1 : 1;
        x = Math.abs(x) / Math.sqrt(2);
        const t = 1.0 / (1.0 + p * x);
        const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
        return 0.5 * (1.0 + sign * y);
    }

    // --- Keyboard shortcut: Enter to calculate ---
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.ctrlKey && !e.shiftKey) {
            const tag = document.activeElement.tagName;
            if (tag === 'INPUT' || tag === 'SELECT') {
                e.preventDefault();
                doCalculate();
            }
        }
    });

    // Initial setup
    updateDaysToExpiry();
    updateLabels();
});
