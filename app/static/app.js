let lastSignalId = null;
let selectedSignalId = null;
let latestSeenSignalId = null;
let currentChartKey = null;
let tradingViewScriptLoading = false;
const LIVE_REFRESH_MS = 5000;
const TRADINGVIEW_SCRIPT_URL = "https://s3.tradingview.com/tv.js";
const PAIR_TO_TV_SYMBOL = {
  EUR_USD: "FX:EURUSD",
  GBP_USD: "FX:GBPUSD",
  USD_JPY: "FX:USDJPY",
  XAU_USD: "FX_IDC:XAUUSD",
  BTC_USDT: "BINANCE:BTCUSDT",
};

const $ = (id) => document.getElementById(id);

function setLoading(button, loading, text) {
  button.disabled = loading;
  if (loading) {
    button.dataset.oldText = button.textContent;
    button.textContent = text || "Loading...";
  } else {
    button.textContent = button.dataset.oldText || button.textContent;
  }
}

function signalClass(signal) {
  if (signal === "BUY") return "buy";
  if (signal === "SELL") return "sell";
  return "wait";
}

function modeTimeframes(mode) {
  if (mode === "scalping") {
    return { analysis: "M15", execution: "M5" };
  }
  return { analysis: "H4", execution: "H1" };
}

function tradingViewInterval(mode) {
  return mode === "scalping" ? "5" : "60";
}

function displayPair(pair) {
  return String(pair || "XAU_USD").replace("_", "/");
}

function safeParseJson(value) {
  try {
    return value ? JSON.parse(value) : {};
  } catch (err) {
    return {};
  }
}

function isPlaceholder(value) {
  return !value || String(value).includes("{{") || String(value).includes("}}");
}

function chartSymbolFromSignal(sig) {
  const raw = safeParseJson(sig?.raw_json);
  if (!isPlaceholder(raw.tickerid) && String(raw.tickerid).includes(":")) {
    return String(raw.tickerid).toUpperCase();
  }

  const exchange = raw.exchange || raw.prefix;
  const ticker = raw.ticker || raw.symbol || raw.pair;
  if (!isPlaceholder(exchange) && !isPlaceholder(ticker)) {
    const compactTicker = String(ticker).replace("/", "").replace("_", "").toUpperCase();
    return `${String(exchange).toUpperCase()}:${compactTicker}`;
  }

  const pair = sig?.pair || $("pair").value;
  return PAIR_TO_TV_SYMBOL[pair] || PAIR_TO_TV_SYMBOL.XAU_USD;
}

function loadTradingViewScript() {
  if (window.TradingView) return Promise.resolve();
  if (tradingViewScriptLoading) {
    return new Promise((resolve, reject) => {
      const check = window.setInterval(() => {
        if (window.TradingView) {
          window.clearInterval(check);
          resolve();
        }
      }, 100);
      window.setTimeout(() => {
        window.clearInterval(check);
        reject(new Error("TradingView chart belum bisa dimuat."));
      }, 10000);
    });
  }

  tradingViewScriptLoading = true;
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = TRADINGVIEW_SCRIPT_URL;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Gagal memuat TradingView chart."));
    document.head.appendChild(script);
  });
}

async function renderTradingViewChart(sig = null) {
  const mode = sig?.mode || $("mode").value;
  const symbol = chartSymbolFromSignal(sig);
  const interval = tradingViewInterval(mode);
  const key = `${symbol}:${interval}`;
  const container = $("tradingviewChart");
  if (!container || key === currentChartKey) return;

  currentChartKey = key;
  $("chartTitle").textContent = `${displayPair(sig?.pair || $("pair").value)} - ${symbol}`;
  $("chartMeta").textContent = `${mode.toUpperCase()} execution interval`;
  container.innerHTML = `<div class="chart-loading">Memuat chart TradingView...</div>`;

  try {
    await loadTradingViewScript();
    container.innerHTML = "";
    new window.TradingView.widget({
      autosize: true,
      symbol,
      interval,
      timezone: "Asia/Jakarta",
      theme: "dark",
      style: "1",
      locale: "id",
      enable_publishing: false,
      allow_symbol_change: true,
      hide_side_toolbar: false,
      details: true,
      calendar: false,
      support_host: "https://www.tradingview.com",
      container_id: "tradingviewChart",
    });
  } catch (err) {
    container.innerHTML = `<div class="chart-loading">${err.message}</div>`;
  }
}

function generateWebhookTemplate() {
  const mode = $("mode").value;
  const tf = modeTimeframes(mode);
  const payload = {
    pair: $("pair").value,
    mode,
    analysis_timeframe: tf.analysis,
    execution_timeframe: tf.execution,
    signal: "AUTO",
    analysis_bias: "",
    execution_confirmation: "",
    price: "{{close}}",
    stop_loss: "",
    tp1: "",
    tp2: "",
    tp3: "",
    balance: Number($("balance").value),
    account_type: $("accountType").value,
    risk_percent: Number($("riskPercent").value),
    ticker: "{{ticker}}",
    exchange: "{{exchange}}",
    timeframe: "{{interval}}",
    time: "{{time}}",
    news: "",
    note: "TradingView alert",
  };
  $("webhookTemplate").value = JSON.stringify(payload, null, 2);
  renderTradingViewChart();
}

function renderSignal(sig) {
  lastSignalId = sig.id;
  selectedSignalId = sig.id;
  $("sendBtn").disabled = false;
  const card = $("currentSignal");
  card.className = `card signal-card ${signalClass(sig.signal)}`;
  card.innerHTML = `
    <p class="eyebrow">Sinyal Terakhir</p>
    <h3>${sig.signal} <span class="badge ${signalClass(sig.signal)}">${sig.confidence}%</span></h3>
    <p>${sig.pair} - ${sig.mode.toUpperCase()} - ${sig.status}</p>
  `;

  const detail = [
    `Pair              : ${sig.pair}`,
    `Mode              : ${sig.mode}`,
    `Timeframe Analisis: ${String(sig.h4_bias).replace("ANALYSIS_", "")}`,
    `Timeframe Eksekusi: ${String(sig.h1_confirmation).replace("EXECUTION_", "")}`,
    `Signal            : ${sig.signal}`,
    `Status            : ${sig.status}`,
    `Confidence        : ${sig.confidence}%`,
    `Price             : ${sig.entry_min ?? "-"}`,
    `Stop Loss         : ${sig.stop_loss ?? "-"}`,
    `TP1               : ${sig.take_profit_1 ?? "-"}`,
    `TP2               : ${sig.take_profit_2 ?? "-"}`,
    `TP3               : ${sig.take_profit_3 ?? "-"}`,
    `Risk/Reward       : ${sig.risk_reward ? "1:" + sig.risk_reward : "-"}`,
    `Lot Rekomendasi   : ${sig.lot_size ?? "-"}`,
    `Risk Amount USD   : ${sig.risk_amount_usd ?? "-"}`,
    `Risk Percent      : ${sig.risk_percent}%`,
    `Account           : ${sig.account_type}`,
    `Balance           : ${sig.balance}`,
    ``,
    `Detail:`,
    sig.reason,
  ].join("\n");
  $("signalDetail").textContent = detail;
  $("lastUpdated").textContent = new Date(sig.created_at).toLocaleString();
  renderTradingViewChart(sig);
}

function setLiveStatus(state, message) {
  const el = $("liveStatus");
  el.className = `status live ${state}`;
  el.textContent = message;
}

async function loadHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    $("providerStatus").textContent = `Provider: ${data.provider}`;
    $("aiStatus").textContent = data.ai_reasoning_enabled ? "Active" : "Off";
    $("aiDetail").textContent = data.ai_reasoning_enabled
      ? `Model: ${data.ai_model}`
      : "Reasoning AI belum aktif.";
  } catch (err) {
    $("providerStatus").textContent = "Provider: offline";
    $("aiStatus").textContent = "Offline";
    $("aiDetail").textContent = "Status AI belum tersedia.";
  }
}

async function sendAlert() {
  if (!lastSignalId) return;
  const btn = $("sendBtn");
  setLoading(btn, true, "Mengirim...");
  try {
    const res = await fetch(`/api/send-alert/${lastSignalId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel: $("channel").value }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Gagal kirim alert");
    alert("Alert berhasil dikirim.");
    loadHistory();
  } catch (err) {
    alert(err.message);
  } finally {
    setLoading(btn, false);
  }
}

async function clearHistory() {
  if (!window.confirm("Bersihkan semua riwayat sinyal?")) return;

  const btn = $("clearHistoryBtn");
  setLoading(btn, true, "Menghapus...");
  try {
    const res = await fetch("/api/signals", { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Gagal membersihkan riwayat");

    latestSeenSignalId = null;
    selectedSignalId = null;
    lastSignalId = null;
    $("sendBtn").disabled = true;
    $("history").innerHTML = "";
    $("currentSignal").className = "card signal-card";
    $("currentSignal").innerHTML = `
      <p class="eyebrow">Sinyal Terakhir</p>
      <h3>Belum ada sinyal</h3>
      <p>Menunggu alert dari TradingView.</p>
    `;
    $("signalDetail").textContent = "Belum ada data.";
    $("lastUpdated").textContent = "-";
    $("pollDetail").textContent = `${data.deleted} riwayat dibersihkan.`;
  } catch (err) {
    alert(err.message);
  } finally {
    setLoading(btn, false);
  }
}

async function loadHistory({ auto = false } = {}) {
  let data = [];
  try {
    const res = await fetch("/api/signals?limit=20", { cache: "no-store" });
    data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Gagal memuat sinyal");
    setLiveStatus("ok", "Live: connected");
    $("pollStatus").textContent = "Live";
    $("pollDetail").textContent = `Update terakhir: ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    setLiveStatus("error", "Live: disconnected");
    $("pollStatus").textContent = "Offline";
    $("pollDetail").textContent = err.message || "Tidak bisa mengambil data terbaru.";
    return;
  }
  const history = $("history");
  history.innerHTML = "";
  data.forEach((sig) => {
    const div = document.createElement("div");
    div.className = "history-item";
    div.innerHTML = `
      <strong>${sig.pair} <span class="badge ${signalClass(sig.signal)}">${sig.signal}</span></strong>
      <div>${new Date(sig.created_at).toLocaleString()}</div>
      <div>Mode: ${sig.mode} - Confidence: ${sig.confidence}%</div>
      <div>Status: ${sig.status}</div>
    `;
    div.onclick = () => renderSignal(sig);
    history.appendChild(div);
  });

  if (!data.length) {
    latestSeenSignalId = null;
    if (!auto) {
      $("pollDetail").textContent = "Belum ada sinyal dari TradingView.";
    }
    return;
  }

  const newest = data[0];
  const hasNewSignal = newest.id !== latestSeenSignalId;
  latestSeenSignalId = newest.id;
  if (hasNewSignal || !selectedSignalId || selectedSignalId === lastSignalId) {
    renderSignal(newest);
  }
}

function startLiveUpdates() {
  setLiveStatus("pending", "Live: connecting");
  loadHistory();
  window.setInterval(() => loadHistory({ auto: true }), LIVE_REFRESH_MS);
}

$("sendBtn").addEventListener("click", sendAlert);
$("refreshBtn").addEventListener("click", loadHistory);
$("clearHistoryBtn").addEventListener("click", clearHistory);
["pair", "mode", "balance", "accountType", "riskPercent"].forEach((id) => {
  $(id).addEventListener("input", generateWebhookTemplate);
  $(id).addEventListener("change", generateWebhookTemplate);
});

generateWebhookTemplate();
renderTradingViewChart();
loadHealth();
startLiveUpdates();
