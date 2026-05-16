const WEBHOOK_URL = "https://trading-signal-one.vercel.app/webhook/tradingview";
const WEBHOOK_SECRET = "";
const GMAIL_QUERY = 'from:(tradingview.com) newer_than:6h';
const MAX_THREADS = 20;
const MAX_PROCESSED_IDS = 500;
const PROCESSED_IDS_KEY = "processedTradingViewEmailIds";

function forwardTradingViewEmails() {
  const processedIds = loadProcessedIds();
  const processedSet = new Set(processedIds);
  const threads = GmailApp.search(GMAIL_QUERY, 0, MAX_THREADS);
  const newProcessedIds = [];

  threads.forEach((thread) => {
    thread.getMessages().forEach((message) => {
      const messageId = message.getId();
      if (processedSet.has(messageId)) return;

      const body = message.getPlainBody() || "";
      const jsonText = extractFirstJsonObject(body);
      if (!jsonText) {
        newProcessedIds.push(messageId);
        console.log(`No JSON payload found in email: ${message.getSubject()}`);
        return;
      }

      let payload;
      try {
        payload = JSON.parse(jsonText);
      } catch (error) {
        newProcessedIds.push(messageId);
        console.log(`Invalid JSON payload in email ${messageId}: ${error}`);
        return;
      }

      if (WEBHOOK_SECRET && !payload.secret) {
        payload.secret = WEBHOOK_SECRET;
      }

      const response = UrlFetchApp.fetch(WEBHOOK_URL, {
        method: "post",
        contentType: "application/json",
        payload: JSON.stringify(payload),
        muteHttpExceptions: true,
      });

      const status = response.getResponseCode();
      const text = response.getContentText();
      console.log(`Forwarded email ${messageId}. Status: ${status}. Body: ${text}`);

      if (status >= 200 && status < 300) {
        newProcessedIds.push(messageId);
      }
    });
  });

  if (newProcessedIds.length) {
    saveProcessedIds(processedIds.concat(newProcessedIds).slice(-MAX_PROCESSED_IDS));
  }
}

function extractFirstJsonObject(text) {
  let start = -1;
  let depth = 0;
  let inString = false;
  let escaped = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];

    if (start === -1) {
      if (char === "{") {
        start = index;
        depth = 1;
      }
      continue;
    }

    if (escaped) {
      escaped = false;
      continue;
    }

    if (char === "\\") {
      escaped = true;
      continue;
    }

    if (char === '"') {
      inString = !inString;
      continue;
    }

    if (inString) continue;

    if (char === "{") depth += 1;
    if (char === "}") depth -= 1;

    if (depth === 0) {
      return text.slice(start, index + 1);
    }
  }

  return "";
}

function loadProcessedIds() {
  const raw = PropertiesService.getScriptProperties().getProperty(PROCESSED_IDS_KEY);
  if (!raw) return [];

  try {
    const ids = JSON.parse(raw);
    return Array.isArray(ids) ? ids : [];
  } catch (error) {
    return [];
  }
}

function saveProcessedIds(ids) {
  PropertiesService.getScriptProperties().setProperty(PROCESSED_IDS_KEY, JSON.stringify(ids));
}
