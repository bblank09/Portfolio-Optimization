// Illustrative backtest engine — deterministic (seeded) sample-data generator.
// SAMPLE DATA ONLY: no real prices are fetched. Seeded from the run's own inputs so
// identical inputs reproduce identical output (reproducibility, not real history).

function hashSeed(str) {
  let h = 1779033703 ^ str.length;
  for (let i = 0; i < str.length; i++) {
    h = Math.imul(h ^ str.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return () => {
    h = Math.imul(h ^ (h >>> 16), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  };
}
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function gauss(rand) {
  let u = 0, v = 0;
  while (u === 0) u = rand();
  while (v === 0) v = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}
const mean = (a) => (a.length ? a.reduce((s, x) => s + x, 0) / a.length : 0);
const std = (a) => { const mu = mean(a); return Math.sqrt(mean(a.map((x) => (x - mu) ** 2))); };

// [meanAnnual, volAnnual, dividendYieldAnnual, marketBeta(correlation to shared factor)] — illustrative.
const ASSET_PROFILES = {
  SPY: [0.10, 0.155, 0.013, 0.98], AAPL: [0.19, 0.30, 0.005, 0.55], MSFT: [0.17, 0.27, 0.008, 0.6],
  GOOGL: [0.15, 0.28, 0.0, 0.55], AMZN: [0.16, 0.33, 0.0, 0.5], TSLA: [0.20, 0.55, 0.0, 0.4],
  QQQ: [0.14, 0.21, 0.006, 0.9], VTI: [0.10, 0.16, 0.014, 0.97], BND: [0.03, 0.06, 0.025, 0.05],
  GLD: [0.06, 0.15, 0.0, 0.02], IWM: [0.09, 0.21, 0.012, 0.75], EFA: [0.07, 0.18, 0.02, 0.7],
};
function profileFor(ticker) { return ASSET_PROFILES[(ticker || "").toUpperCase()] || [0.09, 0.20, 0.012, 0.5]; }

function monthsBetween(start, end) {
  const s = new Date(start), e = new Date(end);
  return Math.max(12, (e.getFullYear() - s.getFullYear()) * 12 + (e.getMonth() - s.getMonth()));
}
function addMonths(dateStr, n) { const d = new Date(dateStr); d.setMonth(d.getMonth() + n); return d.toISOString().slice(0, 10); }
function freqToMonths(freq) { return { monthly: 1, quarterly: 3, semiannual: 6, annual: 12 }[freq] || 1; }

function solveIRRMonthly(cashflows) {
  const npv = (r) => cashflows.reduce((s, cf) => s + cf.amount / Math.pow(1 + r, cf.t), 0);
  let lo = -0.3, hi = 1.0, flo = npv(lo), fhi = npv(hi);
  if (flo * fhi > 0) { hi = 3; fhi = npv(hi); if (flo * fhi > 0) return null; }
  for (let i = 0; i < 80; i++) {
    const mid = (lo + hi) / 2, fm = npv(mid);
    if (Math.abs(fm) < 1e-6) return mid;
    if (flo * fm < 0) { hi = mid; fhi = fm; } else { lo = mid; flo = fm; }
  }
  return (lo + hi) / 2;
}

export function generateResults(input) {
  const { portfolio, benchmark, startDate, endDate, initialCapital, rebalanceMode, cashflow,
    annualDrag, transactionCost, slippageBps, riskFreeRate, useAdjClose, reinvestDividends } = input;
  const seedFn = hashSeed(JSON.stringify(input));
  const rand = mulberry32(Math.floor(seedFn() * 1e9));

  const nMonths = monthsBetween(startDate, endDate);
  const targetW = portfolio.map((p) => p.weight / 100);
  const profiles = portfolio.map((p) => profileFor(p.ticker));
  const [benchMeanA, benchVolA, benchDivA, benchRho] = profileFor(benchmark);
  const includeDividends = !!(useAdjClose && reinvestDividends);
  const dragMonthly = (annualDrag || 0) / 100 / 12;
  const costBps = (Number(transactionCost) || 0) + (Number(slippageBps) || 0);
  const rf = (riskFreeRate != null ? riskFreeRate : 2) / 100;

  const rebalEveryM = rebalanceMode === "none" ? 0 : freqToMonths(rebalanceMode);
  const cfOn = !!(cashflow && cashflow.enabled);
  const cfAmount = cfOn ? Number(cashflow.amount) || 0 : 0;
  const cfSign = cfOn && cashflow.type === "withdrawal" ? -1 : 1;
  const cfFreqM = cfOn ? freqToMonths(cashflow.frequency) : 0;

  let assetValues = targetW.map((w) => w * initialCapital);
  let benchVal = initialCapital, invested = initialCapital;
  const dates = [startDate], portfolioValues = [initialCapital], benchmarkValues = [initialCapital], netInvested = [initialCapital];
  const cashflowEvents = [], rebalanceEvents = [];
  const monthlyPortReturns = [], monthlyBenchReturns = [];
  const assetMonthlyReturns = portfolio.map(() => []);
  const irrCashflows = [{ t: 0, amount: -initialCapital }];

  for (let m = 1; m <= nMonths; m++) {
    const d = addMonths(startDate, m);
    const zMarket = gauss(rand);
    const prevTotal = assetValues.reduce((a, b) => a + b, 0);

    const doCf = cfOn && cfFreqM > 0 && m % cfFreqM === 0 &&
      (!cashflow.start || d >= cashflow.start) && (!cashflow.end || d <= cashflow.end);
    const cfVal = doCf ? cfSign * cfAmount : 0;
    if (doCf && cashflow.timing !== "end") {
      const w = assetValues.map((v) => v / prevTotal);
      assetValues = assetValues.map((v, i) => v + cfVal * w[i]);
      invested += cfVal;
    }
    const baseTotal = assetValues.reduce((a, b) => a + b, 0);

    assetValues = assetValues.map((v, i) => {
      const [meanA, volA, divA, rho] = profiles[i];
      const idio = gauss(rand);
      let r = meanA / 12 + (volA / Math.sqrt(12)) * (rho * zMarket + Math.sqrt(1 - rho * rho) * idio) - dragMonthly;
      if (includeDividends) r += divA / 12;
      assetMonthlyReturns[i].push(r);
      return v * (1 + r);
    });
    const idioB = gauss(rand);
    let rb = benchMeanA / 12 + (benchVolA / Math.sqrt(12)) * (benchRho * zMarket + Math.sqrt(1 - benchRho * benchRho) * idioB);
    if (includeDividends) rb += benchDivA / 12;
    benchVal *= 1 + rb;

    let afterReturnTotal = assetValues.reduce((a, b) => a + b, 0);
    const rp = afterReturnTotal / baseTotal - 1;

    if (doCf && cashflow.timing === "end") {
      const w = assetValues.map((v) => v / afterReturnTotal);
      assetValues = assetValues.map((v, i) => v + cfVal * w[i]);
      benchVal += cfVal; invested += cfVal;
    }
    if (doCf) {
      cashflowEvents.push({ date: d, type: cashflow.type, amount: Math.abs(cfVal), runningInvested: Math.round(invested) });
      irrCashflows.push({ t: m, amount: -cfVal });
    }

    if (rebalEveryM > 0 && m % rebalEveryM === 0) {
      const total = assetValues.reduce((a, b) => a + b, 0);
      const before = assetValues.map((v) => v / total);
      const turnover = targetW.reduce((s, w, i) => s + Math.abs(w - before[i]), 0) / 2;
      const costDrag = turnover * (costBps / 10000);
      const afterCostTotal = total * (1 - costDrag);
      assetValues = targetW.map((w) => w * afterCostTotal);
      rebalanceEvents.push({
        date: d, turnoverPct: turnover * 100, costDrag: costDrag * 100,
        before: portfolio.map((p, i) => ({ ticker: p.ticker, weight: before[i] * 100 })),
        after: portfolio.map((p, i) => ({ ticker: p.ticker, weight: targetW[i] * 100 })),
      });
    }

    dates.push(d);
    portfolioValues.push(assetValues.reduce((a, b) => a + b, 0));
    benchmarkValues.push(benchVal);
    netInvested.push(invested);
    monthlyPortReturns.push(rp);
    monthlyBenchReturns.push(rb);
  }
  irrCashflows.push({ t: nMonths, amount: portfolioValues[portfolioValues.length - 1] });

  const years = nMonths / 12;
  const twrrCagr = Math.pow(monthlyPortReturns.reduce((a, r) => a * (1 + r), 1), 12 / monthlyPortReturns.length) - 1;
  const benchCagr = Math.pow(benchmarkValues.at(-1) / initialCapital, 1 / years) - 1;
  const vol = std(monthlyPortReturns) * Math.sqrt(12);
  const rfM = rf / 12;
  const excessR = monthlyPortReturns.map((r) => r - rfM);
  const sharpe = std(excessR) ? (mean(excessR) / std(excessR)) * Math.sqrt(12) : 0;
  const downside = monthlyPortReturns.filter((r) => r < rfM).map((r) => (r - rfM) ** 2);
  const downsideDev = Math.sqrt(mean(downside.length ? downside : [0])) * Math.sqrt(12);
  const sortino = downsideDev ? ((mean(monthlyPortReturns) - rfM) * 12) / downsideDev : 0;

  let peak = portfolioValues[0], benchPeak = benchmarkValues[0];
  const ddSeries = portfolioValues.map((v) => { peak = Math.max(peak, v); return v / peak - 1; });
  const benchDdSeries = benchmarkValues.map((v) => { benchPeak = Math.max(benchPeak, v); return v / benchPeak - 1; });
  const maxDD = Math.min(...ddSeries), benchMaxDD = Math.min(...benchDdSeries);
  const calmar = maxDD !== 0 ? twrrCagr / Math.abs(maxDD) : 0;
  const ulcerIndex = Math.sqrt(mean(ddSeries.map((d) => d * d))) * 100;

  const mp = mean(monthlyPortReturns), mb = mean(monthlyBenchReturns);
  const covPB = mean(monthlyPortReturns.map((r, i) => (r - mp) * (monthlyBenchReturns[i] - mb)));
  const varB = mean(monthlyBenchReturns.map((r) => (r - mb) ** 2));
  const beta = varB ? covPB / varB : 0;
  const alpha = twrrCagr - (rf + beta * (benchCagr - rf));
  const diffR = monthlyPortReturns.map((r, i) => r - monthlyBenchReturns[i]);
  const trackingError = std(diffR) * Math.sqrt(12);
  const informationRatio = trackingError ? (mean(diffR) * 12) / trackingError : 0;
  const correlation = (std(monthlyPortReturns) * std(monthlyBenchReturns)) ? covPB / (std(monthlyPortReturns) * std(monthlyBenchReturns)) : 0;

  const irrMonthly = solveIRRMonthly(irrCashflows);
  const mwrr = irrMonthly != null ? (Math.pow(1 + irrMonthly, 12) - 1) * 100 : null;

  // annual & monthly grids
  const annualReturns = [];
  for (let y = 0; y < Math.ceil(years); y++) {
    const slice = monthlyPortReturns.slice(y * 12, y * 12 + 12), bSlice = monthlyBenchReturns.slice(y * 12, y * 12 + 12);
    if (!slice.length) continue;
    const yearNum = new Date(startDate).getFullYear() + y + 1;
    const pr = slice.reduce((a, r) => a * (1 + r), 1) - 1, br = bSlice.reduce((a, r) => a * (1 + r), 1) - 1;
    annualReturns.push({ year: yearNum, portfolio: pr * 100, benchmark: br * 100, diff: (pr - br) * 100 });
  }
  const monthlyGrid = [];
  for (let y = 0; y < Math.ceil(years); y++) {
    const slice = monthlyPortReturns.slice(y * 12, y * 12 + 12);
    if (!slice.length) continue;
    monthlyGrid.push({ year: new Date(startDate).getFullYear() + y + 1, months: slice.map((r) => r * 100) });
  }
  const flatMonths = monthlyPortReturns.map((r, i) => ({ r: r * 100, d: dates[i + 1] }));
  const bestMonth = flatMonths.reduce((a, b) => (b.r > a.r ? b : a));
  const worstMonth = flatMonths.reduce((a, b) => (b.r < a.r ? b : a));
  const bestYear = annualReturns.reduce((a, b) => (b.portfolio > a.portfolio ? b : a), annualReturns[0]);
  const worstYear = annualReturns.reduce((a, b) => (b.portfolio < a.portfolio ? b : a), annualReturns[0]);

  // rolling 12-month metrics
  const rollingDates = [], rollingReturn = [], rollingVol = [], rollingSharpe = [], rollingBeta = [];
  for (let i = 12; i <= monthlyPortReturns.length; i++) {
    const win = monthlyPortReturns.slice(i - 12, i), bWin = monthlyBenchReturns.slice(i - 12, i);
    const rr = win.reduce((a, r) => a * (1 + r), 1) - 1;
    const rv = std(win) * Math.sqrt(12);
    const rex = win.map((r) => r - rfM);
    const rs = std(rex) ? (mean(rex) / std(rex)) * Math.sqrt(12) : 0;
    const mWin = mean(win), mbWin = mean(bWin);
    const covWin = mean(win.map((r, j) => (r - mWin) * (bWin[j] - mbWin)));
    const varWin = mean(bWin.map((r) => (r - mbWin) ** 2));
    rollingDates.push(dates[i]); rollingReturn.push(rr * 100); rollingVol.push(rv * 100); rollingSharpe.push(rs); rollingBeta.push(varWin ? covWin / varWin : 0);
  }

  // return distribution
  const nBins = 10;
  const rMin = Math.min(...monthlyPortReturns) * 100, rMax = Math.max(...monthlyPortReturns) * 100;
  const binW = (rMax - rMin) / nBins || 1;
  const histogram = Array.from({ length: nBins }, (_, i) => ({ from: rMin + i * binW, to: rMin + (i + 1) * binW, count: 0 }));
  monthlyPortReturns.forEach((r) => {
    const pct = r * 100;
    let idx = Math.floor((pct - rMin) / binW);
    idx = Math.max(0, Math.min(nBins - 1, idx));
    histogram[idx].count++;
  });
  const mReturns = mean(monthlyPortReturns), sReturns = std(monthlyPortReturns) || 1e-9;
  const skewness = mean(monthlyPortReturns.map((r) => Math.pow((r - mReturns) / sReturns, 3)));
  const kurtosis = mean(monthlyPortReturns.map((r) => Math.pow((r - mReturns) / sReturns, 4))) - 3;

  // drawdown periods (top 5 by depth)
  const periods = [];
  let curStart = 0, inDD = false, curPeakVal = portfolioValues[0];
  for (let i = 0; i < portfolioValues.length; i++) {
    if (!inDD && ddSeries[i] < -0.0001) { inDD = true; curStart = i; curPeakVal = i > 0 ? Math.max(...portfolioValues.slice(0, i + 1)) : portfolioValues[0]; }
    if (inDD && ddSeries[i] >= -0.0001) {
      periods.push({ startIdx: curStart, endIdx: i });
      inDD = false;
    }
  }
  if (inDD) periods.push({ startIdx: curStart, endIdx: -1 });
  const drawdownPeriods = periods.map((p) => {
    const slice = ddSeries.slice(p.startIdx, p.endIdx === -1 ? undefined : p.endIdx + 1);
    let troughOffset = 0, troughVal = 0;
    slice.forEach((v, i) => { if (v < troughVal) { troughVal = v; troughOffset = i; } });
    return {
      start: dates[p.startIdx], trough: dates[p.startIdx + troughOffset],
      recovery: p.endIdx === -1 ? null : dates[p.endIdx],
      depthPct: troughVal * 100,
      durationMonths: (p.endIdx === -1 ? portfolioValues.length - 1 : p.endIdx) - p.startIdx,
    };
  }).sort((a, b) => a.depthPct - b.depthPct).slice(0, 5);

  // correlation matrix (assets + benchmark)
  const labels = portfolio.map((p) => p.ticker).concat([benchmark + " (bmk)"]);
  const allSeries = assetMonthlyReturns.concat([monthlyBenchReturns]);
  const correlationMatrix = allSeries.map((a) => allSeries.map((b) => {
    const ma = mean(a), mb2 = mean(b);
    const cov = mean(a.map((v, i) => (v - ma) * (b[i] - mb2)));
    const sa = std(a), sb = std(b);
    return (sa && sb) ? cov / (sa * sb) : 0;
  }));

  const totalContrib = cashflowEvents.filter((e) => e.type === "contribution").reduce((s, e) => s + e.amount, 0);
  const totalWithdraw = cashflowEvents.filter((e) => e.type === "withdrawal").reduce((s, e) => s + e.amount, 0);
  const endValue = portfolioValues.at(-1);
  const netInvestedFinal = invested;

  return {
    dates, portfolioValues, benchmarkValues, netInvested, ddSeries, benchDdSeries,
    cashflowEvents, rebalanceEvents, annualReturns, monthlyGrid, bestMonth, worstMonth, bestYear, worstYear,
    monthlyPortReturns, monthlyBenchReturns, rollingDates, rollingReturn, rollingVol, rollingSharpe, rollingBeta,
    histogram, skewness, kurtosis, drawdownPeriods, correlationMatrix, correlationLabels: labels,
    targetWeights: portfolio.map((p, i) => ({ ticker: p.ticker, weight: p.weight })),
    finalWeights: portfolio.map((p, i) => ({ ticker: p.ticker, weight: (assetValues[i] / portfolioValues.at(-1)) * 100 })),
    metrics: {
      endValue, benchEndValue: benchmarkValues.at(-1),
      totalReturnTWRR: (Math.pow(1 + twrrCagr, years) - 1) * 100,
      cagr: twrrCagr * 100, benchCagr: benchCagr * 100, excessReturn: (twrrCagr - benchCagr) * 100,
      vol: vol * 100, sharpe, sortino, calmar, maxDD: maxDD * 100, benchMaxDD: benchMaxDD * 100, ulcerIndex,
      beta, alpha: alpha * 100, trackingError: trackingError * 100, informationRatio, correlation,
      rebalanceCount: rebalanceEvents.length, avgTurnover: rebalanceEvents.length ? mean(rebalanceEvents.map((e) => e.turnoverPct)) : 0,
      totalContrib, totalWithdraw, netInvestedFinal, netProfit: endValue - netInvestedFinal,
      endOverInvested: netInvestedFinal ? endValue / netInvestedFinal : null, mwrr,
      years, riskFreeRateUsed: rf * 100, dividendsIncluded: includeDividends,
    },
  };
}
