const cloud = require("wx-server-sdk");

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
});

const ENV_PREFIX =
  "cloud://cloud1-d1gyc1194235175cf.636c-cloud1-d1gyc1194235175cf-1476104411";

const HISTORY_FILE_ID = `${ENV_PREFIX}/production_history.json`;
const LATEST_FILE_ID = `${ENV_PREFIX}/latest.json`;

const MODEL_START = "2015-01-05";
const VERIFY_END = "2026-08-04";
const NEW_START = "2026-08-05";
const FREEZE_DATE = "2026-08-04";

const COST = 0.001;

function nowText() {
  const d = new Date();
  const pad = n => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  );
}

function finite(v) {
  return typeof v === "number" && Number.isFinite(v);
}

function num(v) {
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
}

function clean(v) {
  if (v === undefined) return null;
  if (typeof v === "number" && !Number.isFinite(v)) return null;
  return v;
}

async function downloadJson(fileID) {
  const res = await cloud.downloadFile({ fileID });
  return JSON.parse(res.fileContent.toString("utf8"));
}

async function uploadJson(cloudPath, obj) {
  return cloud.uploadFile({
    cloudPath,
    fileContent: Buffer.from(
      JSON.stringify(obj, null, 2),
      "utf8"
    )
  });
}

async function saveStatus(status, message, extra = {}) {
  const obj = {
    time: nowText(),
    status,
    message,
    ...extra
  };

  try {
    await uploadJson("model_update_status.json", obj);
  } catch (e) {
    console.error("status upload failed:", e);
  }

  return obj;
}

function asRows(history) {
  if (Array.isArray(history)) return history;
  if (history && Array.isArray(history.data)) return history.data;
  throw new Error("production_history.json 结构无法识别");
}

// ---------------- Array helpers ----------------

function shift(arr, n) {
  const out = new Array(arr.length).fill(null);
  for (let i = n; i < arr.length; i++) {
    out[i] = finite(arr[i - n]) ? arr[i - n] : null;
  }
  return out;
}

function pctChangeN(arr, n) {
  const out = new Array(arr.length).fill(null);
  for (let i = n; i < arr.length; i++) {
    const a = arr[i];
    const b = arr[i - n];
    if (finite(a) && finite(b) && b !== 0) {
      out[i] = (a / b - 1) * 100;
    }
  }
  return out;
}

function rollingMin(arr, window) {
  const out = new Array(arr.length).fill(null);
  for (let i = window - 1; i < arr.length; i++) {
    let m = Infinity;
    let ok = true;
    for (let j = i - window + 1; j <= i; j++) {
      const v = arr[j];
      if (!finite(v)) {
        ok = false;
        break;
      }
      if (v < m) m = v;
    }
    if (ok) out[i] = m;
  }
  return out;
}

function rollingMax(arr, window) {
  const out = new Array(arr.length).fill(null);
  for (let i = window - 1; i < arr.length; i++) {
    let m = -Infinity;
    let ok = true;
    for (let j = i - window + 1; j <= i; j++) {
      const v = arr[j];
      if (!finite(v)) {
        ok = false;
        break;
      }
      if (v > m) m = v;
    }
    if (ok) out[i] = m;
  }
  return out;
}

function rollingStdSample(arr, window) {
  const out = new Array(arr.length).fill(null);

  for (let i = window - 1; i < arr.length; i++) {
    let sum = 0;
    let ok = true;

    for (let j = i - window + 1; j <= i; j++) {
      const v = arr[j];
      if (!finite(v)) {
        ok = false;
        break;
      }
      sum += v;
    }

    if (!ok) continue;

    const mean = sum / window;
    let ss = 0;

    for (let j = i - window + 1; j <= i; j++) {
      const d = arr[j] - mean;
      ss += d * d;
    }

    out[i] = Math.sqrt(ss / (window - 1));
  }

  return out;
}

function rollingPercentileAverage(arr, window) {
  const out = new Array(arr.length).fill(null);

  for (let i = window - 1; i < arr.length; i++) {
    const current = arr[i];
    if (!finite(current)) continue;

    let less = 0;
    let equal = 0;
    let ok = true;

    for (let j = i - window + 1; j <= i; j++) {
      const v = arr[j];

      if (!finite(v)) {
        ok = false;
        break;
      }

      if (v < current) less++;
      else if (v === current) equal++;
    }

    if (!ok) continue;

    const averageRank = less + (equal + 1) / 2;
    out[i] = averageRank / window * 100;
  }

  return out;
}

function calculatePhase(close, threshold) {
  const out = new Array(close.length).fill("UNKNOWN");

  let state = "UNKNOWN";
  let runningHigh = null;
  let runningLow = null;
  let swingHigh = null;
  let swingLow = null;

  for (let i = 0; i < close.length; i++) {
    const c = close[i];

    if (!finite(c)) {
      out[i] = state;
      continue;
    }

    if (state === "UNKNOWN") {
      if (!finite(runningHigh)) {
        runningHigh = c;
        runningLow = c;
      } else {
        runningHigh = Math.max(runningHigh, c);
        runningLow = Math.min(runningLow, c);
      }

      if (c <= runningHigh * (1 - threshold)) {
        state = "DOWN";
        swingLow = c;
      } else if (c >= runningLow * (1 + threshold)) {
        state = "UP";
        swingHigh = c;
      }
    } else if (state === "UP") {
      swingHigh = finite(swingHigh) ? Math.max(swingHigh, c) : c;

      if (c <= swingHigh * (1 - threshold)) {
        state = "DOWN";
        swingLow = c;
      }
    } else if (state === "DOWN") {
      swingLow = finite(swingLow) ? Math.min(swingLow, c) : c;

      if (c >= swingLow * (1 + threshold)) {
        state = "UP";
        swingHigh = c;
      }
    }

    out[i] = state;
  }

  return out;
}

function setFrom(arr) {
  return new Set(arr);
}

function sortedDiff(a, b) {
  return [...a].filter(x => !b.has(x)).sort();
}

// ============================================================
// Build all indicators from the six raw fields.
// ============================================================

function buildIndicators(rows) {
  rows = [...rows].sort((a, b) =>
    String(a.date).localeCompare(String(b.date))
  );

  const date = rows.map(r => String(r.date));
  const allA = rows.map(r => num(r.all_a_close));
  const hs300 = rows.map(r => num(r.hs300_close));
  const zz1000 = rows.map(r => num(r.zz1000_close));
  const turnover = rows.map(r => num(r.turnover));
  const turnoverRate = rows.map(r => num(r.turnover_rate));
  const financing = rows.map(r => num(r.financing_balance));

  const ret1 = new Array(rows.length).fill(null);
  for (let i = 1; i < rows.length; i++) {
    if (finite(allA[i]) && finite(allA[i - 1]) && allA[i - 1] !== 0) {
      ret1[i] = allA[i] / allA[i - 1] - 1;
    }
  }

  const ret5 = pctChangeN(allA, 5);
  const ret63 = pctChangeN(allA, 63);

  const low20 = rollingMin(allA, 20);
  const low60 = rollingMin(allA, 60);
  const low120 = rollingMin(allA, 120);
  const high20 = rollingMax(allA, 20);
  const high60 = rollingMax(allA, 60);

  const up20 = allA.map((v, i) =>
    finite(v) && finite(low20[i]) ? (v / low20[i] - 1) * 100 : null
  );

  const up60 = allA.map((v, i) =>
    finite(v) && finite(low60[i]) ? (v / low60[i] - 1) * 100 : null
  );

  const up120 = allA.map((v, i) =>
    finite(v) && finite(low120[i]) ? (v / low120[i] - 1) * 100 : null
  );

  const dd20 = allA.map((v, i) =>
    finite(v) && finite(high20[i]) ? (v / high20[i] - 1) * 100 : null
  );

  const dd60 = allA.map((v, i) =>
    finite(v) && finite(high60[i]) ? (v / high60[i] - 1) * 100 : null
  );

  const distance20High = dd20.map(v => finite(v) ? -v : null);

  const rv20 = rollingStdSample(ret1, 20);
  const rv120 = rollingStdSample(ret1, 120);

  const rvRatio = rv20.map((v, i) =>
    finite(v) && finite(rv120[i]) && rv120[i] !== 0
      ? v / rv120[i]
      : null
  );

  const rvP252 = rollingPercentileAverage(rvRatio, 252);
  const rvP756 = rollingPercentileAverage(rvRatio, 756);
  const ret63P756 = rollingPercentileAverage(ret63, 756);

  const turnoverAmtP252 = rollingPercentileAverage(turnover, 252);
  const turnoverRateP252 = rollingPercentileAverage(turnoverRate, 252);

  const styleRatio = zz1000.map((v, i) =>
    finite(v) && finite(hs300[i]) && hs300[i] !== 0
      ? v / hs300[i]
      : null
  );

  const styleHigh20 = rollingMax(styleRatio, 20);

  const styleDd20 = styleRatio.map((v, i) =>
    finite(v) && finite(styleHigh20[i]) && styleHigh20[i] !== 0
      ? (1 - v / styleHigh20[i]) * 100
      : null
  );

  const finance63Growth = new Array(rows.length).fill(null);
  for (let i = 63; i < rows.length; i++) {
    if (
      finite(financing[i]) &&
      finite(financing[i - 63]) &&
      financing[i - 63] !== 0
    ) {
      finance63Growth[i] =
        (financing[i] / financing[i - 63] - 1) * 100;
    }
  }

  const finance63GrowthP756 =
    rollingPercentileAverage(finance63Growth, 756);

  const phase5 = calculatePhase(allA, 0.05);
  const phase9 = calculatePhase(allA, 0.09);

  // Execution risk layer.
  const rv60 = rollingStdSample(ret1, 60);
  const rv60P756 = rollingPercentileAverage(rv60, 756);

  return {
    rows,
    date,
    allA,
    ret5,
    up20,
    up60,
    up120,
    dd20,
    dd60,
    distance20High,
    rvP252,
    rvP756,
    ret63P756,
    turnoverAmtP252,
    turnoverRateP252,
    styleDd20,
    finance63GrowthP756,
    phase5,
    phase9,
    rv60P756
  };
}

// ============================================================
// Current production formal signal state machine.
// ============================================================

function buildSignals(ind) {
  const start0 = ind.date.findIndex(d => d >= MODEL_START);
  if (start0 < 0) throw new Error("找不到 MODEL_START");

  const n = ind.date.length - start0;

  const date = ind.date.slice(start0);
  const phase5 = ind.phase5.slice(start0);
  const phase9 = ind.phase9.slice(start0);

  const take = arr => arr.slice(start0);

  const up20 = take(ind.up20);
  const up60 = take(ind.up60);
  const up120 = take(ind.up120);
  const dd20 = take(ind.dd20);
  const dd60 = take(ind.dd60);
  const distance20High = take(ind.distance20High);
  const ret5 = take(ind.ret5);
  const rvP252 = take(ind.rvP252);
  const rvP756 = take(ind.rvP756);
  const ret63P756 = take(ind.ret63P756);
  const turnoverAmtP252 = take(ind.turnoverAmtP252);
  const turnoverRateP252 = take(ind.turnoverRateP252);
  const styleDd20 = take(ind.styleDd20);
  const financeP756 = take(ind.finance63GrowthP756);

  const top5A = new Array(n).fill(false);
  const top5B = new Array(n).fill(false);
  const top5Hard = new Array(n).fill(false);
  const top5Formal = new Array(n).fill(false);
  const top5Route = new Array(n).fill("");

  for (let i = 0; i < n; i++) {
    top5A[i] =
      phase5[i] === "UP" &&
      finite(up60[i]) && up60[i] >= 8 &&
      finite(turnoverAmtP252[i]) && turnoverAmtP252[i] >= 79 &&
      finite(distance20High[i]) && distance20High[i] <= 1 &&
      finite(ret5[i]) && ret5[i] >= 1;

    top5B[i] =
      phase5[i] === "UP" &&
      finite(rvP756[i]) && rvP756[i] >= 60 &&
      finite(ret63P756[i]) && ret63P756[i] <= 20 &&
      finite(up20[i]) && up20[i] >= 4 &&
      finite(ret5[i]) && ret5[i] >= 0;

    top5Hard[i] = top5A[i] || top5B[i];
  }

  let lastSignal = null;
  let lastPhase = null;

  for (let i = 0; i < n; i++) {
    const phase = phase5[i];

    if (phase !== lastPhase) {
      lastSignal = null;
      lastPhase = phase;
    }

    if (
      phase === "UP" &&
      top5Hard[i] &&
      (lastSignal === null || i - lastSignal > 15)
    ) {
      top5Formal[i] = true;

      const routes = [];
      if (top5A[i]) routes.push("A");
      if (top5B[i]) routes.push("B");
      top5Route[i] = routes.join("/");

      lastSignal = i;
    }
  }

  const top9A = new Array(n).fill(false);
  const top9B = new Array(n).fill(false);
  const top9C = new Array(n).fill(false);
  const top9F = new Array(n).fill(false);

  for (let i = 0; i < n; i++) {
    top9A[i] =
      finite(turnoverRateP252[i]) && turnoverRateP252[i] >= 75 &&
      finite(up120[i]) && up120[i] >= 10;

    top9B[i] =
      finite(rvP756[i]) && rvP756[i] >= 50 &&
      finite(styleDd20[i]) && styleDd20[i] >= 2;

    top9C[i] =
      finite(turnoverAmtP252[i]) && turnoverAmtP252[i] >= 85 &&
      finite(up120[i]) && up120[i] >= 10 &&
      finite(styleDd20[i]) && styleDd20[i] >= 2;

    top9F[i] =
      finite(financeP756[i]) &&
      financeP756[i] <= 85;
  }

  const rawTop9 = [];

  for (let i = 0; i < n; i++) {
    if (!top5Formal[i]) continue;

    const A = top9A[i];
    const B = top9B[i];
    const C = top9C[i];
    const F = top9F[i];

    if (A || B || C) {
      if (F) {
        const routes = [];
        if (A) routes.push("A");
        if (B) routes.push("B");
        if (C) routes.push("C");

        rawTop9.push({
          index: i,
          candidateIndex: i,
          deferred: false,
          route: routes.join("/")
        });
      }
      continue;
    }

    for (let j = i + 1; j < Math.min(i + 7, n); j++) {
      if (phase5[j] !== "UP") break;

      if (top9B[j] && top9F[j]) {
        rawTop9.push({
          index: j,
          candidateIndex: i,
          deferred: true,
          route: "B"
        });
        break;
      }
    }
  }

  const rawByDay = new Map();
  for (const x of rawTop9) {
    if (!rawByDay.has(x.index)) rawByDay.set(x.index, x);
  }

  const top9Formal = new Array(n).fill(false);
  const top9Route = new Array(n).fill("");
  const top9Deferred = new Array(n).fill(false);
  const top9CandidateDate = new Array(n).fill("");

  lastSignal = null;

  for (const i of [...rawByDay.keys()].sort((a, b) => a - b)) {
    const x = rawByDay.get(i);

    if (lastSignal === null || i - lastSignal > 15) {
      top9Formal[i] = true;
      top9Route[i] = x.route;
      top9Deferred[i] = x.deferred;
      top9CandidateDate[i] = date[x.candidateIndex];
      lastSignal = i;
    }
  }

  // Bottom-5.
  const bottom5RvEffective = rvP756.map((v, i) =>
    finite(v) ? v : rvP252[i]
  );

  const bottom5ANonphase = new Array(n).fill(false);
  const bottom5ABase = new Array(n).fill(false);
  const bottom5B = new Array(n).fill(false);
  const bottom5C = new Array(n).fill(false);

  for (let i = 0; i < n; i++) {
    bottom5ANonphase[i] =
      finite(dd20[i]) && dd20[i] <= -4 &&
      finite(ret5[i]) && ret5[i] <= -2.4 &&
      finite(bottom5RvEffective[i]) && bottom5RvEffective[i] >= 40;

    bottom5ABase[i] =
      phase5[i] === "DOWN" &&
      bottom5ANonphase[i];

    bottom5B[i] =
      phase5[i] === "DOWN" &&
      finite(dd60[i]) && dd60[i] <= -9 &&
      finite(ret63P756[i]) && ret63P756[i] <= 60 &&
      finite(rvP756[i]) && rvP756[i] >= 70 &&
      finite(ret5[i]) && ret5[i] <= 0;

    bottom5C[i] =
      phase5[i] === "DOWN" &&
      finite(dd60[i]) && dd60[i] <= -8 &&
      finite(ret63P756[i]) && ret63P756[i] <= 50 &&
      finite(rvP756[i]) && rvP756[i] <= 15 &&
      finite(ret5[i]) && ret5[i] <= -4.5;
  }

  const bottom5A = new Array(n).fill(false);
  const bottom5M = new Array(n).fill(false);

  let phaseAge = 0;
  let previousPhase = null;

  for (let i = 0; i < n; i++) {
    const phase = phase5[i];

    if (phase !== previousPhase) phaseAge = 1;
    else phaseAge += 1;

    let A = bottom5ABase[i];
    const B = bottom5B[i];
    const C = bottom5C[i];

    if (A) {
      const pureA = !B && !C;

      if (pureA && phaseAge >= 2) {
        A = finite(dd60[i]) && dd60[i] <= -7.5;
      }
    }

    bottom5A[i] = A;

    const newDown =
      phase === "DOWN" &&
      (i === 0 || phase5[i - 1] !== "DOWN");

    if (newDown) {
      const start = Math.max(0, i - 5);
      let inherited = false;

      for (let j = start; j < i; j++) {
        if (bottom5ANonphase[j]) {
          inherited = true;
          break;
        }
      }

      bottom5M[i] = inherited;
    }

    previousPhase = phase;
  }

  const bottom5Hard = new Array(n).fill(false);
  const bottom5Formal = new Array(n).fill(false);
  const bottom5Route = new Array(n).fill("");

  for (let i = 0; i < n; i++) {
    bottom5Hard[i] =
      bottom5A[i] ||
      bottom5B[i] ||
      bottom5C[i] ||
      bottom5M[i];
  }

  lastSignal = null;
  lastPhase = null;

  for (let i = 0; i < n; i++) {
    const phase = phase5[i];

    if (phase !== lastPhase) {
      lastSignal = null;
      lastPhase = phase;
    }

    if (
      phase === "DOWN" &&
      bottom5Hard[i] &&
      (lastSignal === null || i - lastSignal > 22)
    ) {
      bottom5Formal[i] = true;

      const routes = [];
      if (bottom5A[i]) routes.push("A");
      if (bottom5B[i]) routes.push("B");
      if (bottom5C[i]) routes.push("C");
      if (bottom5M[i]) routes.push("M");

      bottom5Route[i] = routes.join("/");
      lastSignal = i;
    }
  }

  // Bottom-9.
  const bottom9A = new Array(n).fill(false);
  const bottom9B = new Array(n).fill(false);
  const bottom9C = new Array(n).fill(false);
  const bottom9Hard = new Array(n).fill(false);
  const bottom9Formal = new Array(n).fill(false);
  const bottom9Route = new Array(n).fill("");

  for (let i = 0; i < n; i++) {
    bottom9A[i] =
      phase9[i] === "DOWN" &&
      finite(dd20[i]) && dd20[i] <= -4 &&
      finite(ret5[i]) && ret5[i] <= -3.8 &&
      finite(rvP756[i]) && rvP756[i] >= 55;

    bottom9B[i] =
      phase9[i] === "DOWN" &&
      finite(dd60[i]) && dd60[i] <= -12.5 &&
      finite(ret63P756[i]) && ret63P756[i] <= 60 &&
      finite(rvP756[i]) && rvP756[i] >= 50 &&
      finite(ret5[i]) && ret5[i] <= 0;

    bottom9C[i] =
      phase9[i] === "DOWN" &&
      finite(dd60[i]) && dd60[i] <= -9 &&
      finite(ret63P756[i]) && ret63P756[i] <= 60 &&
      finite(rvP756[i]) && rvP756[i] <= 15 &&
      finite(ret5[i]) && ret5[i] <= -2;

    bottom9Hard[i] =
      bottom9A[i] ||
      bottom9B[i] ||
      bottom9C[i];
  }

  lastSignal = null;
  lastPhase = null;

  for (let i = 0; i < n; i++) {
    const phase = phase9[i];

    if (phase !== lastPhase) {
      lastSignal = null;
      lastPhase = phase;
    }

    if (
      phase === "DOWN" &&
      bottom9Hard[i] &&
      (lastSignal === null || i - lastSignal > 15)
    ) {
      bottom9Formal[i] = true;

      const routes = [];
      if (bottom9A[i]) routes.push("A");
      if (bottom9B[i]) routes.push("B");
      if (bottom9C[i]) routes.push("C");

      bottom9Route[i] = routes.join("/");
      lastSignal = i;
    }
  }

  return {
    start0,
    date,
    phase5,
    phase9,
    ret5,
    dd20,
    rv60P756: ind.rv60P756.slice(start0),
    top5Formal,
    top5Route,
    top9Formal,
    top9Route,
    top9Deferred,
    top9CandidateDate,
    bottom5Formal,
    bottom5Route,
    bottom9Formal,
    bottom9Route
  };
}

function formalDates(sig, col) {
  const out = [];
  for (let i = 0; i < sig.date.length; i++) {
    if (sig[col][i]) out.push(sig.date[i]);
  }
  return out;
}

function verifyHistorical(sig, latest) {
  const checks = [
    ["Top-5", "top5", "top5Formal"],
    ["Top-9", "top9", "top9Formal"],
    ["Bottom-5", "bottom5", "bottom5Formal"],
    ["Bottom-9", "bottom9", "bottom9Formal"]
  ];

  const result = {};
  let allPass = true;

  for (const [name, key, col] of checks) {
    const target = new Set(
      (latest.strategies[key].formal || [])
        .map(x => x.date)
        .filter(d => d >= MODEL_START && d <= VERIFY_END)
    );

    const got = new Set(
      formalDates(sig, col)
        .filter(d => d <= VERIFY_END)
    );

    const missed = sortedDiff(target, got);
    const extra = sortedDiff(got, target);
    const pass = missed.length === 0 && extra.length === 0;

    result[name] = {
      target_count: target.size,
      calculated_count: got.size,
      missed,
      extra,
      pass
    };

    if (!pass) allPass = false;
  }

  return {
    modules: result,
    pass: allPass
  };
}

// ============================================================
// Incremental execution layer, anchored to frozen production NAV.
// ============================================================

function inferFreezePosition(ind, latest) {
  const backtest = latest.backtest || {};
  const curveDates = backtest.curve_dates || [];
  const curves = backtest.curves || {};
  const strategyCurve = curves["最新拐点执行策略"] || [];

  if (
    !curveDates.length ||
    curveDates.length !== strategyCurve.length
  ) {
    throw new Error("latest.json 缺少完整生产净值曲线");
  }

  const priceMap = new Map();
  for (let i = 0; i < ind.date.length; i++) {
    priceMap.set(ind.date[i], ind.allA[i]);
  }

  const states = [0, 0.25, 0.40, 1.0];
  let position = 1.0;
  const inferredPositions = new Map([[curveDates[0], position]]);
  const changes = [];
  let maxError = 0;

  for (let i = 1; i < curveDates.length; i++) {
    const d0 = curveDates[i - 1];
    const d1 = curveDates[i];

    if (!priceMap.has(d0) || !priceMap.has(d1)) continue;

    const p0 = priceMap.get(d0);
    const p1 = priceMap.get(d1);

    if (!finite(p0) || !finite(p1) || p0 === 0) continue;

    const marketRet = p1 / p0 - 1;
    const nav0 = Number(strategyCurve[i - 1]);
    const nav1 = Number(strategyCurve[i]);

    if (!finite(nav0) || !finite(nav1) || nav0 === 0) continue;

    const observedRatio = nav1 / nav0;

    let best = null;

    for (const target of states) {
      const predictedRatio =
        (1 + position * marketRet) *
        (1 - COST * Math.abs(target - position));

      const error = Math.abs(predictedRatio - observedRatio);

      if (best === null || error < best.error) {
        best = {
          error,
          target
        };
      }
    }

    maxError = Math.max(maxError, best.error);

    if (Math.abs(best.target - position) > 1e-12) {
      changes.push({
        date: d1,
        from: position,
        to: best.target
      });
    }

    position = best.target;
    inferredPositions.set(d1, position);
  }

  if (!inferredPositions.has(FREEZE_DATE)) {
    throw new Error(`无法恢复 ${FREEZE_DATE} 冻结仓位`);
  }

  const freezePosition = inferredPositions.get(FREEZE_DATE);
  const historicalChanges =
    changes.filter(x => x.date <= FREEZE_DATE);

  const pass =
    Math.abs(freezePosition) <= 1e-12 &&
    historicalChanges.length === 55;

  return {
    freeze_position: freezePosition,
    historical_changes: historicalChanges.length,
    expected_changes: 55,
    max_nav_inference_error: maxError,
    pass
  };
}

function buildSignalMap(sig, formalCol, routeCol, extra = {}) {
  const out = new Map();

  for (let i = 0; i < sig.date.length; i++) {
    if (
      sig.date[i] >= NEW_START &&
      sig[formalCol][i]
    ) {
      const item = {
        date: sig.date[i],
        route: sig[routeCol][i] || null
      };

      if (extra.deferred) {
        item.deferred = !!sig.top9Deferred[i];
        item.candidate_date = sig.top9CandidateDate[i] || null;
      }

      out.set(sig.date[i], item);
    }
  }

  return out;
}

function calculateExecution(ind, sig, freezeInfo) {
  if (!freezeInfo.pass) {
    throw new Error("冻结执行状态校验未通过");
  }

  const dateToInd = new Map();
  for (let i = 0; i < ind.date.length; i++) {
    dateToInd.set(ind.date[i], i);
  }

  const top9Map = buildSignalMap(
    sig,
    "top9Formal",
    "top9Route",
    { deferred: true }
  );

  const bottom9Map = buildSignalMap(
    sig,
    "bottom9Formal",
    "bottom9Route"
  );

  const bottom5Map = buildSignalMap(
    sig,
    "bottom5Formal",
    "bottom5Route"
  );

  const incrementalDates =
    ind.date.filter(d => d >= NEW_START);

  let currentPosition = 0.0;
  let coreLong = false;

  let pendingSell = null;
  let pendingBuy = null;
  let trial = null;
  let scheduledAction = null;

  const events = [];
  const daily = [];

  function addEvent(date, event, detail, target = null) {
    const x = { date, event, detail };
    if (target !== null) x.target_position = target;
    events.push(x);
  }

  for (let k = 0; k < incrementalDates.length; k++) {
    const date = incrementalDates[k];
    const gi = dateToInd.get(date);

    const closeToday = ind.allA[gi];
    const ret5Today = ind.ret5[gi];
    const dd20Today = ind.dd20[gi];
    const rv60pToday = ind.rv60P756[gi];

    let actionToday = "";

    // T+1 execution.
    if (scheduledAction !== null) {
      const oldPosition = currentPosition;

      if (scheduledAction.set_core !== undefined) {
        coreLong = !!scheduledAction.set_core;
      }

      currentPosition = scheduledAction.target;

      actionToday =
        `${Math.round(oldPosition * 100)}% → ` +
        `${Math.round(currentPosition * 100)}%；` +
        scheduledAction.reason;

      addEvent(
        date,
        Math.abs(oldPosition - currentPosition) > 1e-12
          ? "EXECUTION"
          : "EXECUTION_NO_CHANGE",
        actionToday,
        currentPosition
      );

      scheduledAction = null;
    }

    const top9Today = top9Map.has(date);
    const bottom9Today = bottom9Map.has(date);
    const bottom5Today = bottom5Map.get(date) || null;

    if (top9Today) {
      if (pendingBuy !== null) {
        addEvent(
          date,
          "BUY_PENDING_CANCELLED",
          "Top-9反向信号出现，取消Bottom-9待买。"
        );
        pendingBuy = null;
      }

      if (trial !== null) {
        addEvent(
          date,
          "TRIAL_CANCELLED",
          "Top-9反向信号出现，取消40%试仓。"
        );

        if (Math.abs(currentPosition - 0.40) < 1e-12) {
          scheduledAction = {
            target: 0,
            reason: "Top-9反向信号，退出Bottom-5试仓",
            set_core: false
          };
        }

        trial = null;
      }

      if (pendingSell === null) {
        pendingSell = {
          signal_date: date,
          start_index: k
        };

        addEvent(
          date,
          "TOP9_PENDING_SELL",
          "Top-9正式信号；进入顶部待确认，最长观察30个交易日。"
        );
      }
    }

    if (bottom9Today) {
      if (pendingSell !== null) {
        addEvent(
          date,
          "SELL_PENDING_CANCELLED",
          "Bottom-9反向信号出现，取消Top-9待卖。"
        );
        pendingSell = null;
      }

      if (!coreLong && pendingBuy === null) {
        pendingBuy = {
          signal_date: date,
          start_index: k,
          low: closeToday
        };

        addEvent(
          date,
          "BOTTOM9_PENDING_BUY",
          "Bottom-9正式信号；开始记录信号后最低收盘价，等待反弹7%。"
        );
      }

      if (trial !== null) {
        trial.bottom9_seen = true;
        trial.bottom9_date = date;
      }
    }

    if (bottom5Today !== null) {
      const routes = String(bottom5Today.route || "")
        .split("/")
        .filter(Boolean);

      if (
        routes.includes("M") &&
        !coreLong &&
        trial === null &&
        !top9Today
      ) {
        trial = {
          signal_date: date,
          start_index: k,
          bottom9_seen: bottom9Today
        };

        scheduledAction = {
          target: 0.40,
          reason: "Bottom-5 相位记忆M，建立40%试仓",
          set_core: false
        };

        addEvent(
          date,
          "BOTTOM5_M_TRIAL",
          "Bottom-5 M成立；下一交易日收盘目标40%。"
        );
      }
    }

    // Top confirmation.
    if (pendingSell !== null) {
      const age = k - pendingSell.start_index;

      if (
        age >= 1 &&
        age <= 30 &&
        finite(ret5Today) &&
        ret5Today <= -1.5
      ) {
        addEvent(
          date,
          "TOP9_SELL_CONFIRMED",
          `来源Top-9=${pendingSell.signal_date}；` +
          `ret5=${ret5Today.toFixed(4)}% <= -1.5%；` +
          "下一交易日收盘目标0%。",
          0
        );

        scheduledAction = {
          target: 0,
          reason: "Top-9价格转弱确认",
          set_core: false
        };

        pendingSell = null;
      } else if (age >= 30) {
        addEvent(
          date,
          "TOP9_SELL_EXPIRED",
          "Top-9待卖观察满30个交易日，未完成价格转弱确认。"
        );
        pendingSell = null;
      }
    }

    // Bottom confirmation.
    if (pendingBuy !== null) {
      pendingBuy.low = Math.min(pendingBuy.low, closeToday);

      const age = k - pendingBuy.start_index;
      const rebound = closeToday / pendingBuy.low - 1;

      if (
        age >= 1 &&
        age <= 30 &&
        rebound >= 0.07
      ) {
        addEvent(
          date,
          "BOTTOM9_BUY_CONFIRMED",
          `来源Bottom-9=${pendingBuy.signal_date}；` +
          `最低收盘=${pendingBuy.low.toFixed(2)}；` +
          `反弹=${(rebound * 100).toFixed(2)}% >= 7%；` +
          "下一交易日收盘进入100%核心仓位。",
          1
        );

        scheduledAction = {
          target: 1,
          reason: "Bottom-9反弹7%确认，进入核心仓位",
          set_core: true
        };

        pendingBuy = null;
        trial = null;
      } else if (age >= 30) {
        addEvent(
          date,
          "BOTTOM9_BUY_EXPIRED",
          "Bottom-9待买观察满30个交易日，未完成7%反弹确认。"
        );

        pendingBuy = null;

        if (
          trial !== null &&
          Math.abs(currentPosition - 0.40) < 1e-12
        ) {
          scheduledAction = {
            target: 0,
            reason: "Bottom-9确认超时，退出40%试仓",
            set_core: false
          };
          trial = null;
        }
      }
    }

    if (
      trial !== null &&
      !trial.bottom9_seen
    ) {
      const age = k - trial.start_index;

      if (age >= 10) {
        addEvent(
          date,
          "BOTTOM5_TRIAL_EXPIRED",
          "Bottom-5 M试仓10个交易日内没有Bottom-9升级；下一交易日回到0%。",
          0
        );

        scheduledAction = {
          target: 0,
          reason: "Bottom-5 M试仓超时",
          set_core: false
        };

        trial = null;
      }
    }

    let riskState = "非核心持有";

    if (coreLong) {
      let riskTarget;

      if (finite(dd20Today) && dd20Today <= -8) {
        riskTarget = 0;
        riskState = "一级保护：20日回撤<=-8%";
      } else if (finite(rv60pToday) && rv60pToday >= 90) {
        riskTarget = 0.25;
        riskState = "二级保护：RV60历史分位>=90%";
      } else {
        riskTarget = 1;
        riskState = "正常核心仓位";
      }

      if (
        scheduledAction === null &&
        Math.abs(currentPosition - riskTarget) > 1e-12
      ) {
        scheduledAction = {
          target: riskTarget,
          reason: riskState,
          set_core: true
        };
      }
    }

    daily.push({
      date,
      all_a_close: clean(closeToday),
      ret5_pct: clean(ret5Today),
      dd20_pct: clean(dd20Today),
      rv60_p756: clean(rv60pToday),
      top9_signal: top9Today,
      bottom9_signal: bottom9Today,
      bottom5_signal: bottom5Today !== null,
      position_after_close: currentPosition,
      core_long: coreLong,
      pending_sell_from: pendingSell ? pendingSell.signal_date : null,
      pending_buy_from: pendingBuy ? pendingBuy.signal_date : null,
      trial_from: trial ? trial.signal_date : null,
      risk_state: riskState,
      action_today: actionToday || null,
      next_day_scheduled_target:
        scheduledAction ? scheduledAction.target : null,
      next_day_scheduled_reason:
        scheduledAction ? scheduledAction.reason : null
    });
  }

  const latest = daily[daily.length - 1] || null;

  return {
    events,
    daily,
    latest
  };
}

function collectNewSignals(sig) {
  const keys = [
    ["top5", "top5Formal", "top5Route"],
    ["top9", "top9Formal", "top9Route"],
    ["bottom5", "bottom5Formal", "bottom5Route"],
    ["bottom9", "bottom9Formal", "bottom9Route"]
  ];

  const out = {
    top5: [],
    top9: [],
    bottom5: [],
    bottom9: []
  };

  for (const [key, formalCol, routeCol] of keys) {
    for (let i = 0; i < sig.date.length; i++) {
      if (
        sig.date[i] >= NEW_START &&
        sig[formalCol][i]
      ) {
        const item = {
          date: sig.date[i],
          route: sig[routeCol][i] || null
        };

        if (key === "top9") {
          item.deferred = !!sig.top9Deferred[i];
          item.candidate_date =
            sig.top9CandidateDate[i] || null;
        }

        out[key].push(item);
      }
    }
  }

  return out;
}

function latestSignalDate(arr) {
  if (!arr || !arr.length) return null;
  return arr[arr.length - 1].date;
}

exports.main = async (event, context) => {
  console.log("model_update start:", nowText(), event || {});

  try {
    const [historyObj, latest] = await Promise.all([
      downloadJson(HISTORY_FILE_ID),
      downloadJson(LATEST_FILE_ID)
    ]);

    const rows = asRows(historyObj);

    const required = [
      "date",
      "all_a_close",
      "hs300_close",
      "zz1000_close",
      "turnover",
      "turnover_rate",
      "financing_balance"
    ];

    for (const row of rows) {
      for (const key of required) {
        if (row[key] === undefined || row[key] === null) {
          throw new Error(
            `底账存在缺失字段：date=${row.date}, key=${key}`
          );
        }
      }
    }

    const ind = buildIndicators(rows);
    const sig = buildSignals(ind);

    const historyVerification =
      verifyHistorical(sig, latest);

    if (!historyVerification.pass) {
      const status = await saveStatus(
        "FAIL_HISTORY_SIGNAL_REPRODUCTION",
        "云端JS模型未100%复现历史正式信号，停止输出。",
        {
          history_verification: historyVerification
        }
      );

      return status;
    }

    const freezeInfo =
      inferFreezePosition(ind, latest);

    if (!freezeInfo.pass) {
      const status = await saveStatus(
        "FAIL_EXECUTION_ANCHOR",
        "云端执行层未通过8/4=0%与55/55冻结锚点，停止输出。",
        {
          freeze: freezeInfo
        }
      );

      return status;
    }

    const formalSignals =
      collectNewSignals(sig);

    const execution =
      calculateExecution(ind, sig, freezeInfo);

    const latestDate =
      ind.date[ind.date.length - 1];

    const sigIndex =
      sig.date.findIndex(d => d === latestDate);

    if (sigIndex < 0) {
      throw new Error(
        `最新交易日 ${latestDate} 不在信号状态机区间内`
      );
    }

    const signalsOutput = {
      model_version:
        "current_production_5_9_cloud_js_v1",
      calculated_at: nowText(),
      start: NEW_START,
      end: latestDate,
      history_verification:
        historyVerification.modules,
      formal_signals: formalSignals,
      latest: {
        date: latestDate,
        phase5: sig.phase5[sigIndex],
        phase9: sig.phase9[sigIndex],
        top5_formal:
          !!sig.top5Formal[sigIndex],
        top9_formal:
          !!sig.top9Formal[sigIndex],
        bottom5_formal:
          !!sig.bottom5Formal[sigIndex],
        bottom9_formal:
          !!sig.bottom9Formal[sigIndex]
      }
    };

    const positionOutput = {
      model:
        "current_production_execution_cloud_js_v1",
      calculated_at: nowText(),
      freeze_date: FREEZE_DATE,
      freeze: freezeInfo,
      latest: execution.latest,
      events: execution.events,
      daily: execution.daily
    };

    const runtimeLatest = {
      version: "runtime_latest_v1",
      calculated_at: nowText(),
      date: latestDate,
      market: {
        all_a_close:
          clean(ind.allA[ind.allA.length - 1]),
        phase5: sig.phase5[sigIndex],
        phase9: sig.phase9[sigIndex]
      },
      position: execution.latest
        ? {
            current:
              execution.latest.position_after_close,
            current_pct:
              Math.round(
                execution.latest.position_after_close * 100
              ),
            core_long:
              execution.latest.core_long,
            pending_sell_from:
              execution.latest.pending_sell_from,
            pending_buy_from:
              execution.latest.pending_buy_from,
            trial_from:
              execution.latest.trial_from,
            risk_state:
              execution.latest.risk_state,
            next_day_scheduled_target:
              execution.latest.next_day_scheduled_target,
            next_day_scheduled_reason:
              execution.latest.next_day_scheduled_reason
          }
        : null,
      today_signals: {
        top5: {
          formal: !!sig.top5Formal[sigIndex],
          route: sig.top5Route[sigIndex] || null
        },
        top9: {
          formal: !!sig.top9Formal[sigIndex],
          route: sig.top9Route[sigIndex] || null,
          deferred: !!sig.top9Deferred[sigIndex],
          candidate_date:
            sig.top9CandidateDate[sigIndex] || null
        },
        bottom5: {
          formal: !!sig.bottom5Formal[sigIndex],
          route: sig.bottom5Route[sigIndex] || null
        },
        bottom9: {
          formal: !!sig.bottom9Formal[sigIndex],
          route: sig.bottom9Route[sigIndex] || null
        }
      },
      last_signals: {
        top5: latestSignalDate(formalSignals.top5),
        top9: latestSignalDate(formalSignals.top9),
        bottom5: latestSignalDate(formalSignals.bottom5),
        bottom9: latestSignalDate(formalSignals.bottom9)
      },
      verification: {
        signals_100pct: true,
        execution_anchor_55_of_55: true,
        freeze_position_20260804:
          freezeInfo.freeze_position
      },
      recent_events:
        execution.events.slice(-20)
    };

    await Promise.all([
      uploadJson(
        "calculated_signals_latest.json",
        signalsOutput
      ),
      uploadJson(
        "calculated_position_latest.json",
        positionOutput
      ),
      uploadJson(
        "runtime_latest.json",
        runtimeLatest
      )
    ]);

    const status = await saveStatus(
      "PASS",
      `${latestDate} 云端信号与仓位计算完成。`,
      {
        date: latestDate,
        history_signal_reproduction: true,
        execution_anchor: freezeInfo,
        runtime_latest: runtimeLatest
      }
    );

    console.log(status);
    return status;

  } catch (e) {
    const status = await saveStatus(
      "ERROR",
      `model_update异常：${e.message}`,
      {
        stack: e.stack || null
      }
    );

    console.error(status);
    return status;
  }
};
