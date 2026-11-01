# 📱 POCO X8 Pro (klee) - Xiaomi Global ROM Update Tracker Bot

A **100% serverless**, lightweight, and automated Telegram bot that tracks and alerts on official **Global Fastboot and Recovery** firmware releases for the **POCO X8 Pro** (codename `klee`).

The bot periodically monitors the official GitHub RSS feed every 6 hours and delivers instant alerts directly to Telegram with exact version numbers, MD5 checksums, release dates, changelogs, and direct official download buttons.

---

## ✨ Features

- ⚡ **100% Serverless:** Runs automatically via **GitHub Actions** (or **Cloudflare Workers**) with zero hosting costs and zero server maintenance.
- 🛡️ **Safe & Rate-Limit Proof:** Checking every 6 hours produces only 4 requests per day, well below GitHub or Cloudflare CDN rate limits.
- 🎯 **Strict Global Filter:** Accurately targets the Global ROM branch (`MIXM` / `POCO X8 Pro Global`), automatically filtering out other regional builds (EEA, Russia, India, Turkey, Taiwan, Indonesia, China).
- 🏷️ **Fastboot & Recovery Separation:** Distinct alert messages for Fastboot and Recovery builds. Incremental and OTA delta patches are ignored to ensure only full, flashable ROMs are delivered.
- 📋 **Comprehensive Firmware Information:**
  - Exact version string (e.g. `OS3.0.308.0.WPJMIXM | 16.0`)
  - ROM type (`Fastboot` or `Recovery`)
  - MD5 verification checksum
  - File size
  - Exact release date and time (UTC)
  - Full system changelog
  - Inline Telegram button for one-click direct download from official Xiaomi / Alibaba OSS CDNs
- 💾 **No External Database Required:** Tracks processed MD5 hashes in `known_updates.json`, which is automatically updated and committed back to the repository.

---

## 🚀 Setup & Deployment

### Method 1: GitHub Actions (Recommended)

GitHub Actions runs the tracker on a scheduled cron without requiring any external cloud setup:

1. Stage, commit, and push the repository to GitHub:
   ```bash
   git add .
   git commit -m "feat: serverless update tracker"
   git push origin main
   ```

2. Configure GitHub Secrets:
   - Go to your repository on GitHub.
   - Navigate to **Settings** > **Secrets and variables** > **Actions**.
   - Click **New repository secret** and add:
     - `TELEGRAM_BOT_TOKEN` : Your Telegram bot token (from @BotFather).
     - `TELEGRAM_CHAT_ID`   : Your Telegram chat ID (e.g. `5085388312`).

3. Enable workflow write permissions on GitHub:
   - Under **Settings** > **Actions** > **General**.
   - Under **Workflow permissions**, select **Read and write permissions**.
   - Click **Save**.

4. The workflow (`.github/workflows/tracker.yml`) will run automatically every 6 hours (`0 */6 * * *`).
   - You can also trigger it manually at any time by going to the **Actions** tab, selecting **Check Xiaomi POCO X8 Pro Updates**, and clicking **Run workflow**.

---

### Method 2: Cloudflare Workers (Edge Deployment)

If you prefer deploying to Cloudflare's serverless edge network:

1. Navigate to the `cloudflare` directory:
   ```bash
   cd cloudflare
   ```

2. Deploy using Wrangler CLI:
   ```bash
   npx wrangler deploy
   ```

3. The worker is configured with a Cron Trigger (`0 */6 * * *`) and exports HTTP endpoints:
   - `GET /check` : Triggers an immediate feed check and returns JSON status.
   - `GET /test`  : Sends a test notification to Telegram.

---

## 💻 Local Testing & CLI Options

The tracker script runs on standard Python (3.9+) with zero third-party pip dependencies:

```bash
# Standard run (checks feed and notifies if a new Global build appears)
python tracker.py

# Send a test notification of the latest build to Telegram
python tracker.py --test

# Inspect found updates in the terminal without sending Telegram messages
python tracker.py --check-only

# Force notification for all found Global Fastboot and Recovery builds
python tracker.py --force-notify
```

---

## ⚙️ Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | Bot API token from @BotFather | Pre-configured for @kleeupdatebot |
| `TELEGRAM_CHAT_ID` | Telegram chat/user ID for notifications | Pre-configured admin ID |
| `FEED_URL` | RSS XML feed URL for `klee` | XiaomiFirmwareUpdater GitHub raw feed |
| `DATA_FILE` | Path to persistent JSON state file | `known_updates.json` |

---

## 🤖 Bot Details

- **Bot Name:** POCO X8 Pro Update Tracker
- **Username:** [@kleeupdatebot](https://t.me/kleeupdatebot)
- **Codename:** `klee`
- **Target Branch:** Global (`MIXM`)
