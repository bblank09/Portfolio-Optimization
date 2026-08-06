const objectives = {
  past: {
    title: "Past Performance",
    subtitle: "Historical return and risk",
    description: "Use this when you want to know how a static allocation behaved in the past.",
    required: "portfolio, dates, capital, benchmark",
    optional: "rebalancing, costs",
    preset: { cashflowEnabled: false, cashflowType: "contribution", cashflowAmount: 0, initialCapital: 10000, rebalanceMode: "annual", transactionCost: 0, slippageBps: 0 },
  },
  dca: {
    title: "Monthly DCA",
    subtitle: "Invest every month",
    description: "Use this when you want to model monthly contributions from income or savings.",
    required: "portfolio, monthly amount, dates",
    optional: "timing, rebalance, costs",
    preset: { cashflowEnabled: true, cashflowType: "contribution", cashflowAmount: 500, initialCapital: 10000, rebalanceMode: "annual", transactionCost: 0, slippageBps: 0 },
  },
  withdrawal: {
    title: "Monthly Withdrawal",
    subtitle: "Withdraw every month",
    description: "Use this when you want to test a spending or decumulation plan.",
    required: "portfolio, withdrawal amount, capital",
    optional: "timing, rebalance, costs",
    preset: { cashflowEnabled: true, cashflowType: "withdrawal", cashflowAmount: 1000, initialCapital: 100000, rebalanceMode: "annual", transactionCost: 0, slippageBps: 0 },
  },
  rebalance: {
    title: "Rebalancing Impact",
    subtitle: "Turnover and cost drag",
    description: "Use this when you want to see how rebalancing changes drift, turnover, and cost drag.",
    required: "portfolio, dates, rebalance mode",
    optional: "costs, slippage",
    preset: { cashflowEnabled: false, cashflowType: "contribution", cashflowAmount: 0, initialCapital: 10000, rebalanceMode: "annual", transactionCost: 5, slippageBps: 0 },
  },
};

const formulas = {
  twrr: ["TWRR", "TWRR = product(1 + r_p,t) - 1", "Time-weighted return isolates strategy performance from cashflow timing."],
  mwrr: ["MWRR / IRR", "Solve sum(CF_t / (1 + r)^t) = 0", "Money-weighted return reflects the investor dollar experience."],
  sharpe: ["Sharpe Ratio", "mean(r_p - r_f) / std(r_p - r_f) * sqrt(12)", "Excess return per unit of total volatility."],
  drawdown: ["Maximum Drawdown", "DD_t = V_t / max(V_0..V_t) - 1", "Largest historical peak-to-trough loss."],
  beta: ["Beta", "cov(r_p, r_b) / var(r_b)", "Sensitivity to benchmark returns."],
  alpha: ["Alpha", "CAGR_p - [r_f + beta * (CAGR_b - r_f)]", "Return not explained by benchmark exposure."],
  ulcer: ["Ulcer Index", "sqrt(mean(drawdown_t^2))", "Drawdown depth and persistence in one risk metric."],
};

const tabs = ["Summary", "Overview", "Growth", "Drawdown", "Returns", "Metrics", "Cashflows", "Rebalancing", "Report"];
const palette = ["#5b21d6", "#008b8b", "#9a6700", "#1459a8", "#b42318", "#137a4f"];
const profiles = {
  SPY: [0.10, 0.155, 0.013, 0.98], AAPL: [0.19, 0.30, 0.005, 0.55], MSFT: [0.17, 0.27, 0.008, 0.60],
  QQQ: [0.14, 0.21, 0.006, 0.90], VTI: [0.10, 0.16, 0.014, 0.97], BND: [0.03, 0.06, 0.025, 0.05],
  GLD: [0.06, 0.15, 0.0, 0.02], TSLA: [0.20, 0.55, 0.0, 0.40], AMZN: [0.16, 0.33, 0.0, 0.50],
};

const state = {
  objective: "dca",
  assets: [{ ticker: "AAPL", weight: 30 }, { ticker: "MSFT", weight: 30 }, { ticker: "SPY", weight: 40 }],
  startDate: "2015-01-01",
  endDate: "2025-12-31",
  initialCapital: 10000,
  benchmark: "SPY",
  cashflowEnabled: true,
  cashflowType: "contribution",
  cashflowAmount: 500,
  cashflowFrequency: "monthly",
  cashflowTiming: "end",
  rebalanceMode: "annual",
  riskFreeRate: 2,
  annualDrag: 0,
  transactionCost: 0,
  slippageBps: 0,
  useAdjClose: true,
  reinvestDividends: true,
  activeTab: "Summary",
  advancedOpen: false,
  results: null,
};

function $(id) { return document.getElementById(id); }
function fmtUsd(n) { return "$" + Math.round(Number(n) || 0).toLocaleString("en-US"); }
function fmtPct(n, d = 1) { return n == null ? "n/a" : (Number(n) >= 0 ? "+" : "") + Number(n).toFixed(d) + "%"; }
function pctNoSign(n, d = 1) { return n == null ? "n/a" : Number(n).toFixed(d) + "%"; }
function mean(a) { return a.length ? a.reduce((s, x) => s + x, 0) / a.length : 0; }
function std(a) { const m = mean(a); return Math.sqrt(mean(a.map(x => (x - m) ** 2))); }
function profile(t) { return profiles[String(t || "").toUpperCase()] || [0.09, 0.20, 0.012, 0.50]; }
function freqMonths(f) { return { monthly: 1, quarterly: 3, annual: 12 }[f] || 1; }

function hashSeed(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) h = Math.imul(h ^ str.charCodeAt(i), 16777619);
  return h >>> 0;
}
function rand(seed) {
  let a = seed || 1;
  return () => {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function gauss(r) {
  let u = 0, v = 0;
  while (!u) u = r();
  while (!v) v = r();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}
function monthsBetween(s, e) {
  const a = new Date(s), b = new Date(e);
  return Math.max(1, (b.getFullYear() - a.getFullYear()) * 12 + b.getMonth() - a.getMonth());
}
function addMonths(date, n) {
  const d = new Date(date);
  d.setMonth(d.getMonth() + n);
  return d.toISOString().slice(0, 10);
}
function solveIrr(cfs) {
  const npv = r => cfs.reduce((s, cf) => s + cf.amount / Math.pow(1 + r, cf.t), 0);
  let lo = -0.4, hi = 2, flo = npv(lo), fhi = npv(hi);
  if (flo * fhi > 0) return null;
  for (let i = 0; i < 80; i++) {
    const mid = (lo + hi) / 2, fm = npv(mid);
    if (Math.abs(fm) < 1e-7) return mid;
    if (flo * fm < 0) { hi = mid; fhi = fm; } else { lo = mid; flo = fm; }
  }
  return (lo + hi) / 2;
}

function applyObjective(key) {
  const obj = objectives[key];
  state.objective = key;
  Object.assign(state, obj.preset);
  state.results = null;
  state.activeTab = "Summary";
  syncStateToInputs();
  render();
}

function loadExample() {
  state.assets = [{ ticker: "AAPL", weight: 30 }, { ticker: "MSFT", weight: 30 }, { ticker: "SPY", weight: 40 }];
  applyObjective("dca");
}

function validate() {
  const errors = [];
  const sum = state.assets.reduce((s, a) => s + Number(a.weight || 0), 0);
  const tickers = state.assets.map(a => String(a.ticker || "").trim().toUpperCase());
  if (!state.assets.length) errors.push("Add at least one asset.");
  if (Math.abs(sum - 100) > 0.05) errors.push("Weights sum to " + sum.toFixed(1) + "%, not 100%.");
  if (tickers.some(t => !t)) errors.push("One or more tickers are empty.");
  const dupes = tickers.filter((t, i) => t && tickers.indexOf(t) !== i);
  if (dupes.length) errors.push("Duplicate ticker: " + [...new Set(dupes)].join(", ") + ".");
  if (new Date(state.startDate) >= new Date(state.endDate)) errors.push("Start date must be before end date.");
  if (!(Number(state.initialCapital) > 0)) errors.push("Initial capital must be greater than zero.");
  if (state.cashflowEnabled && Number(state.cashflowAmount) < 0) errors.push("Cashflow amount cannot be negative.");
  return errors;
}

function runBacktest() {
  syncInputsToState();
  const errors = validate();
  if (errors.length) { renderErrors(errors); return; }
  state.results = generateResults();
  state.activeTab = "Summary";
  $("viewReportBtn").disabled = false;
  render();
}

function generateResults() {
  const seed = hashSeed(JSON.stringify(state));
  const r = rand(seed);
  const months = monthsBetween(state.startDate, state.endDate);
  const weights = state.assets.map(a => Number(a.weight) / 100);
  const assetProfiles = state.assets.map(a => profile(a.ticker));
  const benchProfile = profile(state.benchmark);
  const rf = Number(state.riskFreeRate) / 100;
  const includeDiv = state.useAdjClose && state.reinvestDividends;
  const dragM = Number(state.annualDrag) / 100 / 12;
  const costBps = Number(state.transactionCost) + Number(state.slippageBps);
  let assetValues = weights.map(w => w * Number(state.initialCapital));
  let benchmarkValue = Number(state.initialCapital);
  let invested = Number(state.initialCapital);
  const dates = [state.startDate], values = [Number(state.initialCapital)], benchmark = [benchmarkValue], netInvested = [invested];
  const portReturns = [], benchReturns = [], assetReturns = state.assets.map(() => []);
  const cashflows = [], rebalances = [], irrFlows = [{ t: 0, amount: -Number(state.initialCapital) }];
  const cfEvery = freqMonths(state.cashflowFrequency), rebalEvery = state.rebalanceMode === "none" ? 0 : freqMonths(state.rebalanceMode);

  for (let m = 1; m <= months; m++) {
    const date = addMonths(state.startDate, m);
    const market = gauss(r);
    const beforeTotal = assetValues.reduce((s, x) => s + x, 0);
    const doCf = state.cashflowEnabled && m % cfEvery === 0;
    const cfSigned = doCf ? (state.cashflowType === "withdrawal" ? -1 : 1) * Number(state.cashflowAmount) : 0;
    if (doCf && state.cashflowTiming === "beginning") {
      const total = assetValues.reduce((s, x) => s + x, 0);
      assetValues = assetValues.map(v => v + cfSigned * (v / total));
      invested += cfSigned;
    }
    const baseTotal = assetValues.reduce((s, x) => s + x, 0);
    assetValues = assetValues.map((v, i) => {
      const [mu, vol, div, rho] = assetProfiles[i];
      const ar = mu / 12 + (vol / Math.sqrt(12)) * (rho * market + Math.sqrt(1 - rho * rho) * gauss(r)) - dragM + (includeDiv ? div / 12 : 0);
      assetReturns[i].push(ar);
      return v * (1 + ar);
    });
    const [bmu, bvol, bdiv, brho] = benchProfile;
    const br = bmu / 12 + (bvol / Math.sqrt(12)) * (brho * market + Math.sqrt(1 - brho * brho) * gauss(r)) + (includeDiv ? bdiv / 12 : 0);
    benchmarkValue *= 1 + br;
    const afterReturnTotal = assetValues.reduce((s, x) => s + x, 0);
    const pr = afterReturnTotal / baseTotal - 1;
    if (doCf && state.cashflowTiming === "end") {
      const total = assetValues.reduce((s, x) => s + x, 0);
      assetValues = assetValues.map(v => v + cfSigned * (v / total));
      benchmarkValue += cfSigned;
      invested += cfSigned;
    }
    if (doCf) {
      cashflows.push({ date, type: state.cashflowType, amount: Math.abs(cfSigned), running: invested });
      irrFlows.push({ t: m, amount: -cfSigned });
    }
    if (rebalEvery && m % rebalEvery === 0) {
      const total = assetValues.reduce((s, x) => s + x, 0);
      const before = assetValues.map(v => v / total);
      const turnover = weights.reduce((s, w, i) => s + Math.abs(w - before[i]), 0) / 2;
      const cost = turnover * costBps / 10000;
      const afterCost = total * (1 - cost);
      assetValues = weights.map(w => w * afterCost);
      rebalances.push({ date, turnover: turnover * 100, cost: cost * 100, before });
    }
    dates.push(date);
    values.push(assetValues.reduce((s, x) => s + x, 0));
    benchmark.push(benchmarkValue);
    netInvested.push(invested);
    portReturns.push(pr);
    benchReturns.push(br);
  }

  irrFlows.push({ t: months, amount: values.at(-1) });
  const years = months / 12;
  const twrrTotal = portReturns.reduce((a, x) => a * (1 + x), 1) - 1;
  const cagr = Math.pow(1 + twrrTotal, 1 / years) - 1;
  const benchCagr = Math.pow(benchmark.at(-1) / Number(state.initialCapital), 1 / years) - 1;
  const vol = std(portReturns) * Math.sqrt(12);
  const rfM = rf / 12;
  const sharpe = std(portReturns) ? (mean(portReturns.map(x => x - rfM)) / std(portReturns.map(x => x - rfM))) * Math.sqrt(12) : 0;
  const downside = portReturns.filter(x => x < rfM).map(x => (x - rfM) ** 2);
  const sortino = downside.length ? ((mean(portReturns) - rfM) * 12) / (Math.sqrt(mean(downside)) * Math.sqrt(12)) : 0;
  const dd = drawdowns(values), bdd = drawdowns(benchmark);
  const maxDD = Math.min(...dd), benchMaxDD = Math.min(...bdd);
  const ulcer = Math.sqrt(mean(dd.map(x => x * x))) * 100;
  const beta = covariance(portReturns, benchReturns) / (std(benchReturns) ** 2 || 1);
  const alpha = cagr - (rf + beta * (benchCagr - rf));
  const trackingError = std(portReturns.map((x, i) => x - benchReturns[i])) * Math.sqrt(12);
  const infoRatio = trackingError ? mean(portReturns.map((x, i) => x - benchReturns[i])) * 12 / trackingError : 0;
  const corr = covariance(portReturns, benchReturns) / ((std(portReturns) * std(benchReturns)) || 1);
  const irrM = solveIrr(irrFlows);
  const mwrr = irrM == null ? null : Math.pow(1 + irrM, 12) - 1;
  const annual = annualReturns(portReturns, benchReturns);
  const monthly = monthlyGrid(portReturns);
  const hist = histogram(portReturns);
  const drawdownPeriods = worstDrawdowns(dates, values, dd);
  const corrMatrix = correlationMatrix(assetReturns.concat([benchReturns]));
  const labels = state.assets.map(a => a.ticker).concat([state.benchmark + " bmk"]);
  const finalWeights = assetValues.map(v => v / values.at(-1) * 100);
  const rolling = rollingMetrics(dates, portReturns, benchReturns, 12);
  const trailing = trailingReturns(portReturns, benchReturns);
  const monthLeaders = bestWorstMonths(dates, portReturns, benchReturns);
  const assetStats = assetRiskStats(assetReturns, benchReturns, finalWeights);
  const yearlyCashflows = yearlyCashflowSummary(cashflows);
  const rebalanceStats = rebalanceDiagnostics(rebalances, finalWeights);
  const stress = stressScenarios({ cagr, vol, maxDD, beta, trackingError, benchCagr, values, invested });
  return {
    dates, values, benchmark, netInvested, portReturns, benchReturns, dd, bdd,
    cashflows, rebalances, annual, monthly, hist, drawdownPeriods, corrMatrix, labels, finalWeights,
    rolling, trailing, monthLeaders, assetStats, yearlyCashflows, rebalanceStats, stress,
    metrics: {
      endValue: values.at(-1), totalTWRR: twrrTotal * 100, cagr: cagr * 100, benchCagr: benchCagr * 100,
      excess: (cagr - benchCagr) * 100, vol: vol * 100, sharpe, sortino, calmar: maxDD ? cagr / Math.abs(maxDD) : 0,
      maxDD: maxDD * 100, benchMaxDD: benchMaxDD * 100, ulcer, beta, alpha: alpha * 100, trackingError: trackingError * 100,
      infoRatio, corr, totalContrib: sumType(cashflows, "contribution"), totalWithdraw: sumType(cashflows, "withdrawal"),
      netInvested: invested, netProfit: values.at(-1) - invested, endOverInvested: invested ? values.at(-1) / invested : null,
      mwrr: mwrr == null ? null : mwrr * 100, rebalanceCount: rebalances.length,
      avgTurnover: rebalances.length ? mean(rebalances.map(x => x.turnover)) : 0,
      costDrag: rebalances.reduce((s, x) => s + x.cost, 0),
    }
  };
}

function covariance(a, b) { const ma = mean(a), mb = mean(b); return mean(a.map((x, i) => (x - ma) * (b[i] - mb))); }
function drawdowns(values) { let peak = values[0]; return values.map(v => { peak = Math.max(peak, v); return v / peak - 1; }); }
function sumType(rows, type) { return rows.filter(r => r.type === type).reduce((s, r) => s + r.amount, 0); }
function annualReturns(p, b) {
  const out = [];
  for (let i = 0; i < p.length; i += 12) {
    const pr = p.slice(i, i + 12).reduce((a, x) => a * (1 + x), 1) - 1;
    const br = b.slice(i, i + 12).reduce((a, x) => a * (1 + x), 1) - 1;
    out.push({ year: new Date(state.startDate).getFullYear() + 1 + i / 12, p: pr * 100, b: br * 100, diff: (pr - br) * 100 });
  }
  return out;
}
function monthlyGrid(p) {
  const out = [];
  for (let i = 0; i < p.length; i += 12) out.push({ year: new Date(state.startDate).getFullYear() + 1 + i / 12, months: p.slice(i, i + 12).map(x => x * 100) });
  return out;
}
function histogram(returns) {
  const vals = returns.map(x => x * 100), min = Math.min(...vals), max = Math.max(...vals), w = (max - min) / 10 || 1;
  const bins = Array.from({ length: 10 }, (_, i) => ({ from: min + i * w, to: min + (i + 1) * w, count: 0 }));
  vals.forEach(v => bins[Math.max(0, Math.min(9, Math.floor((v - min) / w)))].count++);
  return bins;
}
function worstDrawdowns(dates, values, dd) {
  const periods = [];
  let start = null;
  for (let i = 0; i < dd.length; i++) {
    if (start == null && dd[i] < -0.0001) start = i;
    if (start != null && dd[i] >= -0.0001) { periods.push([start, i]); start = null; }
  }
  if (start != null) periods.push([start, dd.length - 1]);
  return periods.map(([s, e]) => {
    let trough = s;
    for (let i = s; i <= e; i++) if (dd[i] < dd[trough]) trough = i;
    return { start: dates[s], trough: dates[trough], recovery: e === dd.length - 1 ? "Ongoing" : dates[e], depth: dd[trough] * 100, duration: e - s };
  }).sort((a, b) => a.depth - b.depth).slice(0, 5);
}
function correlationMatrix(series) {
  return series.map(a => series.map(b => covariance(a, b) / ((std(a) * std(b)) || 1)));
}
function productReturn(xs) { return xs.reduce((a, x) => a * (1 + x), 1) - 1; }
function rollingMetrics(dates, p, b, window) {
  const out = [];
  for (let i = window; i <= p.length; i++) {
    const ps = p.slice(i - window, i), bs = b.slice(i - window, i);
    const active = ps.map((x, j) => x - bs[j]);
    out.push({
      date: dates[i],
      return: productReturn(ps) * 100,
      benchmark: productReturn(bs) * 100,
      vol: std(ps) * Math.sqrt(12) * 100,
      sharpe: std(ps) ? mean(ps) / std(ps) * Math.sqrt(12) : 0,
      trackingError: std(active) * Math.sqrt(12) * 100,
    });
  }
  return out;
}
function trailingReturns(p, b) {
  const windows = [["1Y", 12], ["3Y", 36], ["5Y", 60], ["Full", p.length]];
  return windows.filter(([, n]) => p.length >= Math.min(n, 12)).map(([label, n]) => {
    const ps = p.slice(-n), bs = b.slice(-n);
    const yrs = ps.length / 12;
    const pr = Math.pow(1 + productReturn(ps), 1 / yrs) - 1;
    const br = Math.pow(1 + productReturn(bs), 1 / yrs) - 1;
    return { label, portfolio: pr * 100, benchmark: br * 100, excess: (pr - br) * 100, vol: std(ps) * Math.sqrt(12) * 100 };
  });
}
function bestWorstMonths(dates, p, b) {
  return p.map((x, i) => ({ date: dates[i + 1], portfolio: x * 100, benchmark: b[i] * 100, diff: (x - b[i]) * 100 }))
    .sort((a, b2) => b2.portfolio - a.portfolio);
}
function assetRiskStats(assetReturns, benchReturns, finalWeights) {
  return assetReturns.map((rs, i) => {
    const total = productReturn(rs);
    const years = rs.length / 12;
    const cagr = Math.pow(1 + total, 1 / years) - 1;
    const vol = std(rs) * Math.sqrt(12);
    const corr = covariance(rs, benchReturns) / ((std(rs) * std(benchReturns)) || 1);
    return {
      ticker: state.assets[i].ticker,
      target: Number(state.assets[i].weight),
      final: finalWeights[i],
      cagr: cagr * 100,
      vol: vol * 100,
      sharpe: std(rs) ? mean(rs) / std(rs) * Math.sqrt(12) : 0,
      bestMonth: Math.max(...rs) * 100,
      worstMonth: Math.min(...rs) * 100,
      corrBenchmark: corr,
    };
  });
}
function yearlyCashflowSummary(cashflows) {
  const byYear = {};
  cashflows.forEach(c => {
    const y = c.date.slice(0, 4);
    byYear[y] ||= { year: y, contribution: 0, withdrawal: 0, count: 0 };
    byYear[y][c.type] += c.amount;
    byYear[y].count += 1;
  });
  return Object.values(byYear);
}
function rebalanceDiagnostics(rebalances, finalWeights) {
  const maxTurnover = rebalances.length ? Math.max(...rebalances.map(x => x.turnover)) : 0;
  const maxCost = rebalances.length ? Math.max(...rebalances.map(x => x.cost)) : 0;
  const drift = state.assets.map((a, i) => ({ ticker: a.ticker, target: Number(a.weight), final: finalWeights[i], drift: finalWeights[i] - Number(a.weight) }));
  return { maxTurnover, maxCost, drift, maxAbsDrift: Math.max(...drift.map(x => Math.abs(x.drift)), 0) };
}
function stressScenarios(x) {
  const end = x.values.at(-1);
  const invested = x.invested || Number(state.initialCapital);
  return [
    { scenario: "Benchmark -10% shock", assumption: "One-month benchmark shock using beta", impact: -10 * x.beta, value: end * (1 - 0.10 * x.beta), note: "Market sensitivity stress" },
    { scenario: "Volatility doubles for 12M", assumption: "Expected return unchanged, volatility x2", impact: -Math.abs(x.vol) * 0.35 * 100, value: end * (1 - Math.abs(x.vol) * 0.35), note: "Risk regime stress" },
    { scenario: "Repeat max drawdown", assumption: "Historical max drawdown repeated", impact: x.maxDD * 100, value: end * (1 + x.maxDD), note: "Path stress" },
    { scenario: "Tracking error shock", assumption: "Underperform benchmark by 1x TE", impact: -x.trackingError * 100, value: end * (1 - x.trackingError), note: "Active risk stress" },
    { scenario: "Break-even vs invested", assumption: "Distance to net invested capital", impact: (end / invested - 1) * 100, value: invested, note: "Capital preservation reference" },
  ];
}
function objectiveChecklist(r) {
  const m = r.metrics;
  const base = [
    ["Benchmark risk acceptable?", `Beta ${m.beta.toFixed(2)}, alpha ${fmtPct(m.alpha)}, tracking error ${pctNoSign(m.trackingError)}`, "Overview / Metrics"],
    ["Worst historical loss visible?", `Max drawdown ${pctNoSign(m.maxDD)}, Ulcer Index ${m.ulcer.toFixed(2)}`, "Drawdown"],
    ["Diversification visible?", `${r.assetStats.length} assets, max final drift ${pctNoSign(r.rebalanceStats.maxAbsDrift)}`, "Metrics / Rebalancing"],
    ["Report export ready?", "Markdown, run config, and metrics JSON available", "Report"],
  ];
  if (state.objective === "past") return [
    ["Did this allocation outperform the benchmark?", `Excess CAGR ${fmtPct(m.excess)} versus ${state.benchmark}`, "Overview"],
    ["Was the return worth the risk?", `Sharpe ${m.sharpe.toFixed(2)}, Sortino ${m.sortino.toFixed(2)}, Calmar ${m.calmar.toFixed(2)}`, "Metrics"],
    ...base,
  ];
  if (state.objective === "dca") return [
    ["How much did the investor put in?", `Total contributed ${fmtUsd(m.totalContrib)}, net invested ${fmtUsd(m.netInvested)}`, "Cashflows"],
    ["What was the dollar outcome?", `Ending value ${fmtUsd(m.endValue)}, net profit ${fmtUsd(m.netProfit)}`, "Summary / Growth"],
    ...base,
  ];
  if (state.objective === "withdrawal") return [
    ["Did the portfolio survive withdrawals?", `${m.endValue > 0 ? "Survived" : "Depleted"} with ending value ${fmtUsd(m.endValue)}`, "Summary"],
    ["How much income was funded?", `Total withdrawn ${fmtUsd(m.totalWithdraw)}`, "Cashflows"],
    ...base,
  ];
  return [
    ["How often did the strategy trade?", `${m.rebalanceCount} rebalance events`, "Rebalancing"],
    ["Was rebalancing cost material?", `Cost drag ${pctNoSign(m.costDrag)}, average turnover ${pctNoSign(m.avgTurnover)}`, "Rebalancing"],
    ...base,
  ];
}

function syncInputsToState() {
  state.startDate = $("startDate").value;
  state.endDate = $("endDate").value;
  state.initialCapital = Number($("initialCapital").value);
  state.benchmark = $("benchmark").value.toUpperCase();
  state.cashflowEnabled = $("cashflowEnabled").value === "true";
  state.cashflowAmount = Number($("cashflowAmount").value);
  state.cashflowType = $("cashflowType").value;
  state.cashflowFrequency = $("cashflowFrequency").value;
  state.cashflowTiming = $("cashflowTiming").value;
  state.rebalanceMode = $("rebalanceMode").value;
  state.riskFreeRate = Number($("riskFreeRate").value);
  state.annualDrag = Number($("annualDrag").value);
  state.transactionCost = Number($("transactionCost").value);
  state.slippageBps = Number($("slippageBps").value);
  state.useAdjClose = $("useAdjClose").value === "true";
  state.reinvestDividends = $("reinvestDividends").value === "true";
}
function syncStateToInputs() {
  $("startDate").value = state.startDate;
  $("endDate").value = state.endDate;
  $("initialCapital").value = state.initialCapital;
  $("benchmark").value = state.benchmark;
  $("cashflowEnabled").value = String(state.cashflowEnabled);
  $("cashflowAmount").value = state.cashflowAmount;
  $("cashflowType").value = state.cashflowType;
  $("cashflowFrequency").value = state.cashflowFrequency;
  $("cashflowTiming").value = state.cashflowTiming;
  $("rebalanceMode").value = state.rebalanceMode;
  $("rebalanceModeMain").value = state.rebalanceMode;
  $("riskFreeRate").value = state.riskFreeRate;
  $("annualDrag").value = state.annualDrag;
  $("transactionCost").value = state.transactionCost;
  $("slippageBps").value = state.slippageBps;
  $("useAdjClose").value = String(state.useAdjClose);
  $("reinvestDividends").value = String(state.reinvestDividends);
}

function render() {
  renderObjectives();
  renderAssets();
  renderInputs();
  renderTabs();
  renderErrors(validate());
  renderContent();
}
function renderObjectives() {
  $("objectives").innerHTML = Object.entries(objectives).map(([key, obj]) => `<button class="objective-card ${state.objective === key ? "active" : ""}" data-key="${key}"><strong>${obj.title}</strong><span>${obj.subtitle}</span></button>`).join("");
  document.querySelectorAll(".objective-card").forEach(btn => btn.onclick = () => applyObjective(btn.dataset.key));
  const obj = objectives[state.objective];
  $("objectiveTitle").textContent = obj.title;
  $("objectiveDescription").textContent = obj.description;
  $("requiredPill").textContent = "Required: " + obj.required;
  $("optionalPill").textContent = "Optional: " + obj.optional;
  $("requiredContext").textContent = obj.title;
}
function renderAssets() {
  $("assets").innerHTML = state.assets.map((a, i) => `
    <div class="asset-row">
      <div><label>Ticker</label><input data-asset="${i}" data-field="ticker" value="${a.ticker}"></div>
      <div><label>Weight %</label><input type="number" data-asset="${i}" data-field="weight" value="${a.weight}"></div>
      <button class="remove" data-remove="${i}">x</button>
    </div>`).join("");
  document.querySelectorAll("[data-asset]").forEach(el => el.oninput = () => {
    const i = Number(el.dataset.asset);
    state.assets[i][el.dataset.field] = el.dataset.field === "weight" ? Number(el.value) : el.value.toUpperCase();
    state.results = null; render();
  });
  document.querySelectorAll("[data-remove]").forEach(el => el.onclick = () => { state.assets.splice(Number(el.dataset.remove), 1); state.results = null; render(); });
  const sum = state.assets.reduce((s, a) => s + Number(a.weight || 0), 0);
  $("weightStatus").textContent = "Total " + sum.toFixed(0) + "%";
  $("allocationBar").innerHTML = state.assets.map(a => `<span style="width:${Math.max(0, Number(a.weight) || 0)}%"></span>`).join("");
}
function renderInputs() {
  $("cashflowAmountWrap").style.display = state.cashflowEnabled ? "" : "none";
  $("cashflowAmountLabel").textContent = state.cashflowType === "withdrawal" ? "Withdrawal amount (USD)" : "Contribution amount (USD)";
  $("rebalanceRequiredWrap").style.display = state.objective === "rebalance" ? "" : "none";
  const opts = [["monthly", "Monthly"], ["quarterly", "Quarterly"], ["annual", "Annual"]];
  $("cashflowFrequency").innerHTML = opts.map(o => `<option value="${o[0]}">${o[1]}</option>`).join("");
  $("cashflowType").innerHTML = `<option value="contribution">Contribution</option><option value="withdrawal">Withdrawal</option>`;
  $("cashflowTiming").innerHTML = `<option value="end">End of period</option><option value="beginning">Beginning of period</option>`;
  const rebal = [["none", "None"], ["monthly", "Monthly"], ["quarterly", "Quarterly"], ["annual", "Annual"]];
  $("rebalanceMode").innerHTML = rebal.map(o => `<option value="${o[0]}">${o[1]}</option>`).join("");
  $("rebalanceModeMain").innerHTML = $("rebalanceMode").innerHTML;
  syncStateToInputs();
  $("assumptionSummary").textContent = `Backtest ${fmtUsd(state.initialCapital)} from ${state.startDate} to ${state.endDate}. Benchmark ${state.benchmark}. ${state.cashflowEnabled ? state.cashflowType + " " + fmtUsd(state.cashflowAmount) + " " + state.cashflowFrequency : "No scheduled cashflow"}. Rebalance ${state.rebalanceMode}.`;
}
function renderTabs() {
  $("tabs").innerHTML = tabs.map(t => `<button class="tab ${state.activeTab === t ? "active" : ""}" data-tab="${t}">${t}</button>`).join("");
  document.querySelectorAll("[data-tab]").forEach(b => b.onclick = () => { state.activeTab = b.dataset.tab; renderContent(); renderTabs(); });
}
function renderErrors(errors) {
  $("errors").innerHTML = errors.map(e => `<div class="error">${e}</div>`).join("");
  $("runBtn").disabled = errors.length > 0;
}
function renderContent() {
  const r = state.results;
  if (!r) { $("content").className = "empty"; $("content").textContent = "Choose an objective, confirm inputs, then run a backtest."; return; }
  $("content").className = "";
  const tab = state.activeTab;
  if (tab === "Summary") renderSummary(r);
  else if (tab === "Overview") renderOverview(r);
  else if (tab === "Growth") renderGrowth(r);
  else if (tab === "Drawdown") renderDrawdown(r);
  else if (tab === "Returns") renderReturns(r);
  else if (tab === "Metrics") renderMetrics(r);
  else if (tab === "Cashflows") renderCashflows(r);
  else if (tab === "Rebalancing") renderRebalancing(r);
  else renderReport(r);
}
function metric(label, value, sub = "") { return `<div class="metric"><div class="label">${label}</div><div class="value">${value}</div>${sub ? `<div class="sub">${sub}</div>` : ""}</div>`; }
function renderSummary(r) {
  const m = r.metrics, obj = objectives[state.objective];
  let text = `${obj.title}: ending value was ${fmtUsd(m.endValue)}, TWRR CAGR was ${fmtPct(m.cagr)}, and max drawdown was ${pctNoSign(m.maxDD)}.`;
  let cards = [metric("Ending value", fmtUsd(m.endValue)), metric("TWRR CAGR", fmtPct(m.cagr)), metric("Max drawdown", pctNoSign(m.maxDD)), metric("Excess vs benchmark", fmtPct(m.excess))];
  if (state.objective === "dca") {
    text = `You contributed ${fmtUsd(m.totalContrib)}. Ending value was ${fmtUsd(m.endValue)}, net profit was ${fmtUsd(m.netProfit)}, and MWRR/IRR was ${fmtPct(m.mwrr)}.`;
    cards = [metric("Total contributed", fmtUsd(m.totalContrib)), metric("Ending value", fmtUsd(m.endValue)), metric("Net profit", fmtUsd(m.netProfit)), metric("MWRR / IRR", fmtPct(m.mwrr))];
  }
  if (state.objective === "withdrawal") {
    text = `You withdrew ${fmtUsd(m.totalWithdraw)}. The portfolio ${m.endValue > 0 ? "remained above zero" : "depleted"} with ending value ${fmtUsd(m.endValue)}.`;
    cards = [metric("Total withdrawn", fmtUsd(m.totalWithdraw)), metric("Ending value", fmtUsd(m.endValue)), metric("Portfolio status", m.endValue > 0 ? "Survived" : "Depleted"), metric("MWRR / IRR", fmtPct(m.mwrr))];
  }
  if (state.objective === "rebalance") {
    text = `The run produced ${m.rebalanceCount} rebalance events, average turnover ${pctNoSign(m.avgTurnover)}, and estimated cost drag ${pctNoSign(m.costDrag)}.`;
    cards = [metric("Rebalance count", m.rebalanceCount), metric("Avg turnover", pctNoSign(m.avgTurnover)), metric("Cost drag", pctNoSign(m.costDrag)), metric("Ending value", fmtUsd(m.endValue))];
  }
  $("content").innerHTML = `
    <div class="panel"><h3>${obj.title} Summary</h3><p class="summary-text">${text}</p></div>
    <div class="metric-grid">${cards.join("")}</div>
    <div class="panel"><h3>Objective checklist</h3>
      ${table(["Question", "Mock answer", "Evidence tab"], objectiveChecklist(r))}
    </div>
    <div class="panel"><h3>Always-on analysis</h3>
      <div class="metric-grid">
        ${metric("Benchmark Risk", "Beta " + m.beta.toFixed(2), "Alpha " + fmtPct(m.alpha) + " · TE " + pctNoSign(m.trackingError))}
        ${metric("Drawdown Stress", pctNoSign(m.maxDD), "Ulcer Index " + m.ulcer.toFixed(2))}
        ${metric("Diversification", r.labels.length + " series", "Max drift " + pctNoSign(r.rebalanceStats.maxAbsDrift))}
        ${metric("CQF Report", "Ready", "Method, formulas, caveats")}
      </div>
    </div>
    <div class="panel"><h3>Stress snapshot</h3>
      ${table(["Scenario", "Assumption", "Impact", "Value after stress"], r.stress.map(s => [s.scenario, s.assumption, fmtPct(s.impact), fmtUsd(s.value)]))}
    </div>`;
}
function renderOverview(r) {
  const m = r.metrics;
  $("content").innerHTML = `<div class="metric-grid">
    ${metric("Ending value", fmtUsd(m.endValue))}${metric("Total return (TWRR)", fmtPct(m.totalTWRR))}
    ${metric("CAGR (TWRR)", fmtPct(m.cagr))}${metric("Volatility", pctNoSign(m.vol))}
    ${metric("Sharpe", m.sharpe.toFixed(2))}${metric("Max drawdown", pctNoSign(m.maxDD))}
    ${metric("Benchmark CAGR", fmtPct(m.benchCagr), state.benchmark)}${metric("Excess return", fmtPct(m.excess))}
    ${metric("MWRR / IRR", fmtPct(m.mwrr), "Investor return with cashflows")}${metric("Net invested", fmtUsd(m.netInvested))}
    ${metric("Tracking error", pctNoSign(m.trackingError))}${metric("Information ratio", m.infoRatio.toFixed(2))}
  </div>
  <div class="panel-grid">
    <div class="panel"><h3>Trailing performance</h3>${table(["Period", "Portfolio", "Benchmark", "Excess", "Volatility"], r.trailing.map(x => [x.label, fmtPct(x.portfolio), fmtPct(x.benchmark), fmtPct(x.excess), pctNoSign(x.vol)]))}</div>
    <div class="panel"><h3>Run assumptions</h3>${table(["Input", "Value"], [
      ["Date range", `${state.startDate} to ${state.endDate}`],
      ["Portfolio", state.assets.map(a => `${a.ticker} ${a.weight}%`).join(", ")],
      ["Benchmark", state.benchmark],
      ["Cashflow", state.cashflowEnabled ? `${state.cashflowType}, ${fmtUsd(state.cashflowAmount)}, ${state.cashflowFrequency}, ${state.cashflowTiming}` : "Disabled"],
      ["Rebalancing", state.rebalanceMode],
      ["Costs", `${state.transactionCost} bps transaction cost, ${state.slippageBps} bps slippage, ${state.annualDrag}% annual drag`],
    ])}</div>
  </div>
  <div class="panel"><h3>Benchmark risk decomposition</h3>${table(["Metric", "Portfolio", "Benchmark / active view", "Interpretation"], [
    ["CAGR", fmtPct(m.cagr), fmtPct(m.benchCagr), "Long-run compounded return"],
    ["Volatility", pctNoSign(m.vol), "Benchmark correlation " + m.corr.toFixed(2), "Total risk and market linkage"],
    ["Beta", m.beta.toFixed(2), "Alpha " + fmtPct(m.alpha), "Systematic exposure and residual return"],
    ["Tracking error", pctNoSign(m.trackingError), "Information ratio " + m.infoRatio.toFixed(2), "Active risk efficiency"],
  ])}</div>`;
}
function path(values, w, h) {
  const min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
  return values.map((v, i) => `${i ? "L" : "M"}${(i / (values.length - 1) * w).toFixed(1)},${(h - ((v - min) / range) * h).toFixed(1)}`).join(" ");
}
function renderGrowth(r) {
  const milestones = [0, Math.floor((r.dates.length - 1) * .25), Math.floor((r.dates.length - 1) * .5), Math.floor((r.dates.length - 1) * .75), r.dates.length - 1];
  $("content").innerHTML = `<div class="metric-grid">
    ${metric("Start value", fmtUsd(r.values[0]), r.dates[0])}${metric("Ending value", fmtUsd(r.values.at(-1)), r.dates.at(-1))}
    ${metric("Net invested", fmtUsd(r.netInvested.at(-1)))}${metric("Benchmark value", fmtUsd(r.benchmark.at(-1)))}
  </div>
  <div class="panel"><h3>Portfolio growth path</h3><div class="legend"><span><i class="dot portfolio"></i>Portfolio</span><span><i class="dot benchmark"></i>Benchmark</span><span><i class="dash"></i>Net invested</span></div>
    <svg class="chart" viewBox="0 0 880 300"><path d="${path(r.netInvested, 880, 280)}" fill="none" stroke="#637083" stroke-dasharray="5 5"/><path d="${path(r.benchmark, 880, 280)}" fill="none" stroke="#008b8b" stroke-width="2"/><path d="${path(r.values, 880, 280)}" fill="none" stroke="#5b21d6" stroke-width="3"/></svg>
  </div>
  <div class="panel"><h3>Value milestones</h3>${table(["Date", "Portfolio", "Benchmark", "Net invested", "Profit over invested"], milestones.map(i => [r.dates[i], fmtUsd(r.values[i]), fmtUsd(r.benchmark[i]), fmtUsd(r.netInvested[i]), fmtUsd(r.values[i] - r.netInvested[i])]))}</div>
  <div class="panel"><h3>Rolling 12M return and volatility</h3>
    <div class="legend"><span><i class="dot portfolio"></i>Rolling return</span><span><i class="dot benchmark"></i>Rolling vol</span></div>
    <svg class="chart small" viewBox="0 0 880 220"><path d="${path(r.rolling.map(x => x.return), 880, 200)}" fill="none" stroke="#5b21d6" stroke-width="2"/><path d="${path(r.rolling.map(x => x.vol), 880, 200)}" fill="none" stroke="#008b8b" stroke-width="2"/></svg>
  </div>`;
}
function renderDrawdown(r) {
  $("content").innerHTML = `<div class="metric-grid">${metric("Worst drawdown", pctNoSign(r.metrics.maxDD))}${metric("Benchmark drawdown", pctNoSign(r.metrics.benchMaxDD))}${metric("Ulcer Index", r.metrics.ulcer.toFixed(2))}</div>
  <div class="panel"><h3>Drawdown path</h3><div class="legend"><span><i class="dot benchmark"></i>Benchmark</span><span><i class="dot red"></i>Portfolio</span></div><svg class="chart" viewBox="0 0 880 260"><path d="${path(r.bdd, 880, 230)}" fill="none" stroke="#008b8b" stroke-width="2"/><path d="${path(r.dd, 880, 230)}" fill="none" stroke="#b42318" stroke-width="2"/></svg></div>
  <div class="panel"><h3>Worst drawdown periods</h3>${table(["Peak", "Trough", "Recovery", "Depth", "Months"], r.drawdownPeriods.map(d => [d.start, d.trough, d.recovery, pctNoSign(d.depth), d.duration]))}</div>
  <div class="panel"><h3>Drawdown stress scenarios</h3>${table(["Scenario", "Assumption", "Impact", "Value after stress", "Note"], r.stress.map(s => [s.scenario, s.assumption, fmtPct(s.impact), fmtUsd(s.value), s.note]))}</div>
  <div class="panel"><h3>Stress interpretation</h3>${table(["Check", "Mock result"], [
    ["Capital at risk", `${fmtUsd(r.metrics.endValue - Math.min(...r.values))} peak-to-trough path loss in the simulated history`],
    ["Recovery pressure", `${r.drawdownPeriods[0]?.duration ?? 0} months in the deepest drawdown period`],
    ["Benchmark stress", `Portfolio beta ${r.metrics.beta.toFixed(2)} means market shocks pass through at about ${pctNoSign(r.metrics.beta * 100)} of benchmark magnitude`],
  ])}</div>`;
}
function renderReturns(r) {
  const max = Math.max(...r.hist.map(b => b.count)) || 1;
  $("content").innerHTML = `<div class="panel"><h3>Annual returns</h3>${table(["Year", "Portfolio", "Benchmark", "Diff"], r.annual.map(a => [a.year, fmtPct(a.p), fmtPct(a.b), fmtPct(a.diff)]))}</div>
  <div class="panel"><h3>Monthly returns heatmap</h3>${r.monthly.map(row => `<div class="heat-row"><span class="heat-year">${row.year}</span>${row.months.map(v => `<span class="heat-cell" title="${fmtPct(v)}" style="background:${v >= 0 ? `rgb(19 122 79 / ${Math.min(.9, Math.abs(v) / 8 + .12)})` : `rgb(180 35 24 / ${Math.min(.9, Math.abs(v) / 8 + .12)})`}"></span>`).join("")}</div>`).join("")}</div>
  <div class="panel"><h3>Monthly return distribution</h3><div class="hist">${r.hist.map(b => `<span class="hist-bar" title="${b.from.toFixed(1)} to ${b.to.toFixed(1)}: ${b.count}" style="height:${Math.max(4, b.count / max * 90)}px;background:${b.from >= 0 ? "#137a4f" : "#b42318"}"></span>`).join("")}</div>${table(["Bin", "Count"], r.hist.map(b => [`${b.from.toFixed(1)}% to ${b.to.toFixed(1)}%`, b.count]))}</div>
  <div class="panel-grid">
    <div class="panel"><h3>Best months</h3>${table(["Date", "Portfolio", "Benchmark", "Diff"], r.monthLeaders.slice(0, 10).map(x => [x.date, fmtPct(x.portfolio), fmtPct(x.benchmark), fmtPct(x.diff)]))}</div>
    <div class="panel"><h3>Worst months</h3>${table(["Date", "Portfolio", "Benchmark", "Diff"], r.monthLeaders.slice(-10).reverse().map(x => [x.date, fmtPct(x.portfolio), fmtPct(x.benchmark), fmtPct(x.diff)]))}</div>
  </div>`;
}
function renderMetrics(r) {
  const m = r.metrics;
  const rows = [
    ["CAGR (TWRR)", fmtPct(m.cagr), "twrr"], ["Volatility", pctNoSign(m.vol), "sharpe"], ["Sharpe", m.sharpe.toFixed(2), "sharpe"],
    ["Sortino", m.sortino.toFixed(2), "sharpe"], ["Calmar", m.calmar.toFixed(2), "drawdown"], ["Beta", m.beta.toFixed(2), "beta"],
    ["Alpha", fmtPct(m.alpha), "alpha"], ["Tracking error", pctNoSign(m.trackingError), "beta"], ["Information ratio", m.infoRatio.toFixed(2), "beta"],
    ["Correlation", m.corr.toFixed(2), "beta"], ["Ulcer Index", m.ulcer.toFixed(2), "ulcer"]
  ];
  $("content").innerHTML = `<div class="panel"><h3>Metrics</h3>${rows.map(x => `<div class="metric-row"><span>${x[0]}</span><span>${x[1]} <button class="formula-btn" data-formula="${x[2]}">f</button></span></div>`).join("")}</div>
  <div class="panel"><h3>Asset risk and allocation</h3>${table(["Ticker", "Target", "Final", "Drift", "CAGR", "Vol", "Sharpe", "Best month", "Worst month", "Corr bmk"], r.assetStats.map(a => [a.ticker, pctNoSign(a.target), pctNoSign(a.final), fmtPct(a.final - a.target), fmtPct(a.cagr), pctNoSign(a.vol), a.sharpe.toFixed(2), fmtPct(a.bestMonth), fmtPct(a.worstMonth), a.corrBenchmark.toFixed(2)]))}</div>
  <div class="panel"><h3>Correlation matrix</h3>${corrTable(r)}</div>
  <div class="panel"><h3>Rolling risk table</h3>${table(["Date", "12M return", "12M benchmark", "12M vol", "12M Sharpe", "12M tracking error"], r.rolling.map(x => [x.date, fmtPct(x.return), fmtPct(x.benchmark), pctNoSign(x.vol), x.sharpe.toFixed(2), pctNoSign(x.trackingError)]))}</div>`;
  document.querySelectorAll("[data-formula]").forEach(b => b.onclick = () => openFormula(b.dataset.formula));
}
function renderCashflows(r) {
  if (!state.cashflowEnabled) { $("content").innerHTML = `<div class="empty">Cashflows are disabled for this objective/run.</div>`; return; }
  const m = r.metrics;
  $("content").innerHTML = `<div class="metric-grid">${metric("Total contributions", fmtUsd(m.totalContrib))}${metric("Total withdrawals", fmtUsd(m.totalWithdraw))}${metric("Net invested", fmtUsd(m.netInvested))}${metric("Net profit", fmtUsd(m.netProfit))}${metric("MWRR / IRR", fmtPct(m.mwrr))}</div>
  <div class="panel"><h3>Yearly cashflow summary</h3>${table(["Year", "Contributions", "Withdrawals", "Events"], r.yearlyCashflows.map(y => [y.year, fmtUsd(y.contribution), fmtUsd(y.withdrawal), y.count]))}</div>
  <div class="panel"><h3>Cashflow events</h3>${table(["Date", "Type", "Amount", "Net invested"], r.cashflows.map(c => [c.date, c.type, fmtUsd(c.amount), fmtUsd(c.running)]))}</div>`;
}
function renderRebalancing(r) {
  if (state.rebalanceMode === "none") { $("content").innerHTML = `<div class="empty">Rebalancing is set to None.</div>`; return; }
  const m = r.metrics;
  $("content").innerHTML = `<div class="metric-grid">${metric("Rebalance count", m.rebalanceCount)}${metric("Avg turnover", pctNoSign(m.avgTurnover))}${metric("Max turnover", pctNoSign(r.rebalanceStats.maxTurnover))}${metric("Cost drag", pctNoSign(m.costDrag))}${metric("Max single cost", pctNoSign(r.rebalanceStats.maxCost, 3))}${metric("Max final drift", pctNoSign(r.rebalanceStats.maxAbsDrift))}</div>
  <div class="panel"><h3>Target vs final allocation</h3>${state.assets.map((a, i) => `<div style="margin-bottom:10px"><div class="hint">${a.ticker}: target ${a.weight}% · final ${r.finalWeights[i].toFixed(1)}%</div><div class="bar"><span style="width:${r.finalWeights[i]}%;background:${palette[i % palette.length]}"></span></div></div>`).join("")}</div>
  <div class="panel"><h3>Allocation drift</h3>${table(["Ticker", "Target", "Final", "Drift"], r.rebalanceStats.drift.map(x => [x.ticker, pctNoSign(x.target), pctNoSign(x.final), fmtPct(x.drift)]))}</div>
  <div class="panel"><h3>Rebalance events</h3>${table(["Date", "Turnover", "Cost drag"], r.rebalances.map(x => [x.date, pctNoSign(x.turnover), pctNoSign(x.cost, 3)]))}</div>`;
}
function renderReport(r) {
  const m = r.metrics;
  const report = [
    ["Objective", objectives[state.objective].title + ": " + objectives[state.objective].description],
    ["Inputs", `${state.assets.map(a => a.ticker + " " + a.weight + "%").join(", ")}. ${state.startDate} to ${state.endDate}. Benchmark ${state.benchmark}.`],
    ["Methodology", "Seeded sample monthly return series -> portfolio value simulation -> cashflow/rebalance events -> metrics/charts/report."],
    ["Performance Results", `Ending value ${fmtUsd(m.endValue)}. TWRR CAGR ${fmtPct(m.cagr)}. MWRR ${fmtPct(m.mwrr)}. Total return ${fmtPct(m.totalTWRR)}. Net profit ${fmtUsd(m.netProfit)}.`],
    ["Benchmark Risk", `Benchmark ${state.benchmark} CAGR ${fmtPct(m.benchCagr)}. Excess return ${fmtPct(m.excess)}. Beta ${m.beta.toFixed(2)}. Alpha ${fmtPct(m.alpha)}. Tracking error ${pctNoSign(m.trackingError)}. Information ratio ${m.infoRatio.toFixed(2)}.`],
    ["Drawdown Stress", `Max drawdown ${pctNoSign(m.maxDD)} versus benchmark ${pctNoSign(m.benchMaxDD)}. Ulcer Index ${m.ulcer.toFixed(2)}. Deepest stress scenario: ${r.stress[2].scenario}, value after stress ${fmtUsd(r.stress[2].value)}.`],
    ["Diversification Check", `Assets: ${r.assetStats.map(a => `${a.ticker} target ${pctNoSign(a.target)}, final ${pctNoSign(a.final)}, corr bmk ${a.corrBenchmark.toFixed(2)}`).join("; ")}.`],
    ["Rebalancing and Cashflows", `Rebalance events ${m.rebalanceCount}. Average turnover ${pctNoSign(m.avgTurnover)}. Cost drag ${pctNoSign(m.costDrag)}. Contributions ${fmtUsd(m.totalContrib)}. Withdrawals ${fmtUsd(m.totalWithdraw)}.`],
    ["CQF Formula Notes", "TWRR = product of sub-period returns; MWRR solves IRR over dated cashflows; Sharpe = annualized excess mean / volatility; beta = covariance with benchmark / benchmark variance; max drawdown = value / running peak - 1."],
    ["Limitations", "Mockup data only. No live prices, corporate actions, taxes, or real Webull CSV import yet."]
  ];
  $("content").innerHTML = `<div class="panel"><h3>Export</h3><button class="btn" id="downloadReport">report.md</button> <button class="btn" id="downloadConfig">run_config.json</button> <button class="btn" id="downloadMetrics">metrics.json</button></div>
  <div class="panel">${report.map(([h, b]) => `<h3>${h}</h3><p class="summary-text">${b}</p>`).join("")}</div>`;
  $("downloadReport").onclick = () => download("report.md", report.map(([h, b]) => `## ${h}\n\n${b}`).join("\n\n"), "text/markdown");
  $("downloadConfig").onclick = () => download("run_config.json", JSON.stringify(state, null, 2), "application/json");
  $("downloadMetrics").onclick = () => download("metrics.json", JSON.stringify(r.metrics, null, 2), "application/json");
}
function table(headers, rows) {
  return `<table><thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(c => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}
function corrTable(r) {
  return `<table><thead><tr><th></th>${r.labels.map(l => `<th class="num">${l}</th>`).join("")}</tr></thead><tbody>${r.labels.map((l, i) => `<tr><th>${l}</th>${r.labels.map((_, j) => `<td class="num">${r.corrMatrix[i][j].toFixed(2)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}
function openFormula(key) {
  const f = formulas[key] || formulas.twrr;
  $("formulaDrawer").classList.remove("hidden");
  $("formulaDrawer").innerHTML = `<button class="btn text" id="closeFormula">Close</button><h2>${f[0]}</h2><pre class="panel">${f[1]}</pre><p class="summary-text">${f[2]}</p>`;
  $("closeFormula").onclick = () => $("formulaDrawer").classList.add("hidden");
}
function download(name, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 500);
}

function bindStatic() {
  $("runBtn").onclick = runBacktest;
  $("viewReportBtn").onclick = () => { state.activeTab = "Report"; render(); };
  $("loadExample").onclick = loadExample;
  $("importCsv").onclick = () => alert("Webull CSV import is a placeholder. Use manual ticker/weight input for this mockup.");
  $("addAsset").onclick = () => { state.assets.push({ ticker: "", weight: 0 }); state.results = null; render(); };
  $("normalizeBtn").onclick = () => {
    const sum = state.assets.reduce((s, a) => s + Number(a.weight || 0), 0) || 1;
    state.assets = state.assets.map(a => ({ ...a, weight: Math.round(Number(a.weight || 0) / sum * 1000) / 10 }));
    state.results = null; render();
  };
  $("toggleAdvanced").onclick = () => { state.advancedOpen = !state.advancedOpen; $("advanced").classList.toggle("open", state.advancedOpen); $("toggleAdvanced").textContent = state.advancedOpen ? "Hide" : "Show"; };
  ["startDate", "endDate", "initialCapital", "benchmark", "cashflowEnabled", "cashflowAmount", "cashflowType", "cashflowFrequency", "cashflowTiming", "rebalanceMode", "rebalanceModeMain", "riskFreeRate", "annualDrag", "transactionCost", "slippageBps", "useAdjClose", "reinvestDividends"].forEach(id => {
    const handler = () => {
      if (id === "rebalanceModeMain") $("rebalanceMode").value = $("rebalanceModeMain").value;
      if (id === "rebalanceMode") $("rebalanceModeMain").value = $("rebalanceMode").value;
      syncInputsToState();
      $("cashflowAmountWrap").style.display = state.cashflowEnabled ? "" : "none";
      $("cashflowAmountLabel").textContent = state.cashflowType === "withdrawal" ? "Withdrawal amount (USD)" : "Contribution amount (USD)";
      state.results = null;
      renderErrors(validate());
      $("assumptionSummary").textContent = `Backtest ${fmtUsd(state.initialCapital)} from ${state.startDate} to ${state.endDate}. Benchmark ${state.benchmark}. ${state.cashflowEnabled ? state.cashflowType + " " + fmtUsd(state.cashflowAmount) + " " + state.cashflowFrequency : "No scheduled cashflow"}. Rebalance ${state.rebalanceMode}.`;
    };
    $(id).oninput = handler;
    $(id).onchange = handler;
  });
}

bindStatic();
syncStateToInputs();
render();
