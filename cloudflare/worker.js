/**
 * Xiaomi POCO X8 Pro (klee) Global ROM Update Tracker
 * Serverless Cloudflare Worker with Cron Triggers
 */

const DEFAULT_FEED_URL = "https://raw.githubusercontent.com/XiaomiFirmwareUpdater/miui-updates-tracker/master/rss/klee.xml";
const DEFAULT_BOT_TOKEN = "";
const DEFAULT_CHAT_ID = "";

export default {
  // Cloudflare Cron Trigger (Runs every 6 hours)
  async scheduled(event, env, ctx) {
    ctx.waitUntil(checkUpdates(env));
  },

  // HTTP Request Handler
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/test") {
      const result = await checkUpdates(env, true);
      return new Response(JSON.stringify(result, null, 2), {
        headers: { "Content-Type": "application/json; charset=utf-8" },
      });
    }

    if (url.pathname === "/check") {
      const result = await checkUpdates(env, false);
      return new Response(JSON.stringify(result, null, 2), {
        headers: { "Content-Type": "application/json; charset=utf-8" },
      });
    }

    // Default status page
    return new Response(
      `POCO X8 Pro (klee) Global ROM Tracker Worker is running! 🚀\n\n` +
      `Endpoints:\n` +
      ` - GET /check  : Check for updates right now\n` +
      ` - GET /test   : Send a test notification to Telegram\n`,
      { headers: { "Content-Type": "text/plain; charset=utf-8" } }
    );
  },
};

/**
 * Main function to fetch feed, parse items, and notify on new Global Fastboot/Recovery ROMs.
 */
async function checkUpdates(env, isTest = false) {
  const feedUrl = env.FEED_URL || DEFAULT_FEED_URL;
  const botToken = env.TELEGRAM_BOT_TOKEN || DEFAULT_BOT_TOKEN;
  const chatId = env.TELEGRAM_CHAT_ID || DEFAULT_CHAT_ID;

  try {
    const response = await fetch(feedUrl, {
      headers: {
        "User-Agent": "XiaomiUpdateTracker-CloudflareWorker/1.0",
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch RSS: ${response.status} ${response.statusText}`);
    }

    const xmlText = await response.text();
    const items = parseXmlFeed(xmlText);

    if (items.length === 0) {
      return { status: "no_global_items_found" };
    }

    // Test mode: Send latest Global update
    if (isTest) {
      const latest = items[items.length - 1];
      const msg = formatTelegramMessage(latest, true);
      const res = await sendTelegramMessage(botToken, chatId, msg, latest.downloadUrl, latest.type);
      return { status: "test_sent", success: res, item: latest };
    }

    // Retrieve known MD5 hashes from Cloudflare KV
    let knownMd5s = [];
    if (env.UPDATES_KV) {
      const stored = await env.UPDATES_KV.get("known_md5s", { type: "json" });
      if (Array.isArray(stored)) {
        knownMd5s = stored;
      }
    }

    const isInitialRun = knownMd5s.length === 0;
    const newItems = items.filter((it) => it.md5 && !knownMd5s.includes(it.md5));

    if (isInitialRun) {
      const latest = items[items.length - 1];
      const welcomeText =
        `🎉 <b>POCO X8 Pro (klee) Update Tracker Activated!</b>\n\n` +
        `You will receive instant alerts whenever a new official <b>Global Fastboot</b> or <b>Recovery</b> update is released.\n\n` +
        `📌 <b>Current Latest Global Build:</b>\n` +
        `• <b>ROM Type:</b> <b>${latest.type}</b>\n` +
        `• <b>Version:</b> <code>${latest.version}</code>\n` +
        `• <b>MD5 Checksum:</b> <code>${latest.md5}</code>\n` +
        `• <b>Release Date:</b> <code>${latest.releaseDate}</code>`;

      await sendTelegramMessage(botToken, chatId, welcomeText, latest.downloadUrl, latest.type);

      const allMd5s = items.map((it) => it.md5).filter(Boolean);
      if (env.UPDATES_KV) {
        await env.UPDATES_KV.put("known_md5s", JSON.stringify(allMd5s));
      }
      return { status: "initialized", knownCount: allMd5s.length };
    }

    if (newItems.length === 0) {
      return { status: "up_to_date", count: items.length };
    }

    // Send notification for each new item
    const notified = [];
    for (const item of newItems) {
      const msg = formatTelegramMessage(item, false);
      const ok = await sendTelegramMessage(botToken, chatId, msg, item.downloadUrl, item.type);
      if (ok) {
        knownMd5s.push(item.md5);
        notified.push(`${item.type}: ${item.version}`);
      }
    }

    if (env.UPDATES_KV) {
      await env.UPDATES_KV.put("known_md5s", JSON.stringify(knownMd5s));
    }

    return { status: "notified", updates: notified };
  } catch (err) {
    console.error("Tracker Error:", err);
    return { status: "error", message: err.message };
  }
}

/**
 * Fast regex XML parser for Xiaomi updates RSS.
 * Strictly extracts ONLY Global Fastboot and Recovery ROMs.
 */
function parseXmlFeed(xml) {
  const itemRegex = /<item>([\s\S]*?)<\/item>/g;
  const updates = [];
  let match;

  while ((match = itemRegex.exec(xml)) !== null) {
    const itemBlock = match[1];

    const titleMatch = itemBlock.match(/<title>([\s\S]*?)<\/title>/);
    const title = titleMatch ? titleMatch[1].trim() : "";

    const descMatch = itemBlock.match(/<description>([\s\S]*?)<\/description>/);
    const desc = descMatch ? descMatch[1].trim() : "";

    // Strictly check for Fastboot or Recovery
    let romType = "";
    if (title.includes("Fastboot") || desc.includes("Fastboot")) {
      romType = "Fastboot";
    } else if (title.includes("Recovery") || desc.includes("Recovery")) {
      romType = "Recovery";
    } else {
      continue;
    }

    const devMatch = desc.match(/Device:\s*<\/b>\s*([^<]+)/);
    const device = devMatch ? devMatch[1].trim() : "";

    const verMatch = desc.match(/Version:\s*<\/b>\s*([^<]+)/);
    const version = verMatch ? verMatch[1].trim() : "";

    // Global filter
    const nonGlobal = ["EEA", "Russia", "India", "Turkey", "Taiwan", "Indonesia", "China"];
    const isNonGlobal = nonGlobal.some(
      (r) => device.toLowerCase().includes(r.toLowerCase()) || title.toLowerCase().includes(r.toLowerCase())
    );

    const isGlobal =
      !isNonGlobal &&
      (device.includes("Global") || version.includes("MIXM") || title.includes("POCO X8 Pro Global"));

    if (!isGlobal) continue;

    const linkMatch = itemBlock.match(/<link>([\s\S]*?)<\/link>/);
    const link = linkMatch ? linkMatch[1].trim() : "";

    const pubDateMatch = itemBlock.match(/<pubDate>([\s\S]*?)<\/pubDate>/);
    const pubDateRaw = pubDateMatch ? pubDateMatch[1].trim() : "";

    const md5Match = desc.match(/MD5:\s*<\/b>\s*([a-fA-F0-9]{32})/);
    const md5 = md5Match ? md5Match[1].trim() : "";

    const sizeMatch = desc.match(/Size:\s*<\/b>\s*([^<]+)/);
    const size = sizeMatch ? sizeMatch[1].trim() : "";

    const dlMatch = desc.match(/Download:\s*<\/b>\s*<a\s+href=['"]([^'"]+)['"]/);
    const downloadUrl = dlMatch ? dlMatch[1].trim() : link;

    let releaseDate = pubDateRaw;
    try {
      const d = new Date(pubDateRaw);
      if (!isNaN(d.getTime())) {
        releaseDate = d.toISOString().replace("T", " ").substring(0, 19) + " UTC";
      }
    } catch (_) {}

    // Changelog
    let changelog = "";
    const clMatch = desc.match(/Changelog:\s*<\/b>\s*<br>([\s\S]*?)(?=<p><b>|$)/);
    if (clMatch) {
      changelog = clMatch[1]
        .replace(/<br\s*\/?>/gi, "\n")
        .replace(/<[^>]+>/g, "")
        .trim();
    }

    updates.push({
      title,
      device: device || "POCO X8 Pro Global",
      type: romType,
      version,
      md5,
      size,
      releaseDate,
      downloadUrl,
      changelog,
    });
  }

  return updates;
}

/**
 * Format English Telegram HTML message.
 */
function formatTelegramMessage(item, isTest = false) {
  const badge = isTest
    ? "🧪 <b>Test Notification - POCO X8 Pro Update Tracker</b>"
    : `🚀 <b>New Global ${item.type} Update Available!</b>`;

  let msg = `${badge}\n\n`;
  msg += `📱 <b>Device:</b> <code>${item.device} (klee)</code>\n`;
  msg += `🏷️ <b>ROM Type:</b> <b>${item.type}</b>\n`;
  msg += `🔢 <b>Version:</b> <code>${item.version}</code>\n`;
  msg += `🔐 <b>MD5 Checksum:</b>\n<code>${item.md5}</code>\n`;
  if (item.size) {
    msg += `📦 <b>File Size:</b> <code>${item.size}</code>\n`;
  }
  msg += `📅 <b>Release Date & Time:</b> <code>${item.releaseDate}</code>\n`;

  if (item.changelog) {
    let cl = item.changelog;
    if (cl.length > 500) cl = cl.substring(0, 500) + "...";
    const clEscaped = cl.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    msg += `\n📋 <b>Changelog:</b>\n<pre>${clEscaped}</pre>\n`;
  }

  return msg;
}

/**
 * Send message via Telegram Bot API with inline download button.
 */
async function sendTelegramMessage(botToken, chatId, text, downloadUrl, romType = "") {
  const payload = {
    chat_id: chatId,
    text: text,
    parse_mode: "HTML",
    disable_web_page_preview: true,
  };

  if (downloadUrl) {
    const buttonLabel = romType ? `📥 Download ${romType} ROM` : "📥 Download Official ROM";
    payload.reply_markup = {
      inline_keyboard: [[{ text: buttonLabel, url: downloadUrl }]],
    };
  }

  const res = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const json = await res.json();
  return json.ok === true;
}
