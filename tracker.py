#!/usr/bin/env python3
"""
Xiaomi Firmware Update Tracker - POCO X8 Pro (klee) Global ROM
Tracks official Global Fastboot & Recovery releases and sends alerts via Telegram.
"""

import sys
import os
import json
import re
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

def load_dotenv():
    """Load simple KEY=VALUE pairs from .env file if present."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("\"'")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

load_dotenv()

FEED_URL = os.environ.get(
    "FEED_URL",
    "https://raw.githubusercontent.com/XiaomiFirmwareUpdater/miui-updates-tracker/master/rss/klee.xml"
)
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DATA_FILE = os.environ.get(
    "DATA_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "known_updates.json")
)

def fetch_feed(url: str) -> str:
    """Fetch the RSS XML feed from GitHub."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) XiaomiUpdateTracker/1.0"
        }
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")

def clean_html_text(text: str) -> str:
    """Remove HTML tags and clean up spacing."""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    lines = [line.strip() for line in text.split("\n")]
    cleaned = "\n".join(l for l in lines if l)
    return cleaned.strip()

def parse_items(xml_content: str):
    """Parse RSS XML and extract ONLY Global Fastboot and Recovery updates."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_content)
    channel = root.find("channel")
    if channel is None:
        return []
    
    updates = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date_raw = (item.findtext("pubDate") or "").strip()
        desc = (item.findtext("description") or "").strip()
        
        # Determine ROM type: ONLY Fastboot or Recovery
        if "Fastboot" in title or "Fastboot" in desc:
            rom_type = "Fastboot"
        elif "Recovery" in title or "Recovery" in desc:
            rom_type = "Recovery"
        else:
            # Skip incremental, OTA, or other types
            continue
            
        # Extract device
        dev_match = re.search(r"Device:\s*</b>\s*([^<]+)", desc)
        device = dev_match.group(1).strip() if dev_match else ""
        
        # Extract version
        ver_match = re.search(r"Version:\s*</b>\s*([^<]+)", desc)
        version = ver_match.group(1).strip() if ver_match else ""
        
        # Identify Global ROM (POCO X8 Pro Global / MIXM)
        # Exclude other regional versions: EEA, Russia, India, Turkey, Taiwan, Indonesia, China
        non_global_regions = ["EEA", "Russia", "India", "Turkey", "Taiwan", "Indonesia", "China"]
        has_non_global = any(r.lower() in device.lower() or r.lower() in title.lower() for r in non_global_regions)
        
        is_global = (
            not has_non_global
            and (
                "Global" in device
                or "MIXM" in version
                or "POCO X8 Pro Global" in title
            )
        )
        
        if not is_global:
            continue
            
        md5_match = re.search(r"MD5:\s*</b>\s*([a-fA-F0-9]{32})", desc)
        md5 = md5_match.group(1).strip() if md5_match else ""
        
        size_match = re.search(r"Size:\s*</b>\s*([^<]+)", desc)
        size = size_match.group(1).strip() if size_match else ""
        
        dl_match = re.search(r"Download:\s*</b>\s*<a\s+href=['\"]([^'\"]+)['\"]", desc)
        download_url = dl_match.group(1).strip() if dl_match else link
        
        # Parse release datetime
        release_date = pub_date_raw
        try:
            dt = parsedate_to_datetime(pub_date_raw)
            dt_utc = dt.astimezone(timezone.utc)
            release_date = dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            release_date = pub_date_raw
            
        # Parse changelog
        changelog = ""
        cl_match = re.search(r"Changelog:\s*</b>\s*<br>(.*?)(?=<p><b>|$)", desc, re.DOTALL)
        if cl_match:
            changelog = clean_html_text(cl_match.group(1))
            
        updates.append({
            "title": title,
            "device": device or "POCO X8 Pro Global",
            "type": rom_type,
            "version": version,
            "md5": md5,
            "size": size,
            "release_date": release_date,
            "pub_date_raw": pub_date_raw,
            "download_url": download_url,
            "changelog": changelog
        })
        
    return updates

def format_telegram_message(item: dict, is_test: bool = False) -> str:
    """Format firmware info into an elegant English HTML message."""
    badge = "🧪 <b>Test Notification - POCO X8 Pro Update Tracker</b>" if is_test else f"🚀 <b>New Global {item['type']} Update Available!</b>"
    
    msg = f"{badge}\n\n"
    msg += f"📱 <b>Device:</b> <code>{item['device']} (klee)</code>\n"
    msg += f"🏷️ <b>ROM Type:</b> <b>{item['type']}</b>\n"
    msg += f"🔢 <b>Version:</b> <code>{item['version']}</code>\n"
    msg += f"🔐 <b>MD5 Checksum:</b>\n<code>{item['md5']}</code>\n"
    if item['size']:
        msg += f"📦 <b>File Size:</b> <code>{item['size']}</code>\n"
    msg += f"📅 <b>Release Date & Time:</b> <code>{item['release_date']}</code>\n"
    
    if item['changelog']:
        short_cl = item['changelog']
        if len(short_cl) > 500:
            short_cl = short_cl[:500] + "..."
        # Escape HTML special chars in changelog
        short_cl_escaped = (
            short_cl.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        msg += f"\n📋 <b>Changelog:</b>\n<pre>{short_cl_escaped}</pre>\n"
        
    return msg

def send_telegram_message(bot_token: str, chat_id: str, text: str, download_url: str = "", rom_type: str = "") -> bool:
    """Send message via Telegram Bot API with an inline button for direct download."""
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    
    if download_url:
        button_label = f"📥 Download {rom_type} ROM" if rom_type else "📥 Download Official ROM"
        payload["reply_markup"] = {
            "inline_keyboard": [
                [
                    {"text": button_label, "url": download_url}
                ]
            ]
        }
        
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("ok", False)
    except Exception as e:
        print(f"[!] Error sending Telegram message: {e}", file=sys.stderr)
        return False

def load_known_updates() -> dict:
    """Load known updates from storage file."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Warning reading {DATA_FILE}: {e}")
    return {"known_md5s": [], "last_check": None}

def save_known_updates(data: dict):
    """Save known updates to storage file."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[!] Error writing {DATA_FILE}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Xiaomi Update Tracker for POCO X8 Pro (klee)")
    parser.add_argument("--test", action="store_true", help="Send a test notification of latest Global update")
    parser.add_argument("--check-only", action="store_true", help="Only check for updates without sending messages")
    parser.add_argument("--force-notify", action="store_true", help="Send notification for all found Global Fastboot & Recovery updates")
    args = parser.parse_args()
    
    print(f"[*] Fetching RSS feed from: {FEED_URL}")
    try:
        xml_content = fetch_feed(FEED_URL)
    except Exception as e:
        print(f"[!] Failed to fetch feed: {e}", file=sys.stderr)
        sys.exit(1)
        
    items = parse_items(xml_content)
    print(f"[*] Found {len(items)} Global Fastboot/Recovery updates in the feed.")
    
    if not args.check_only:
        if not BOT_TOKEN or not CHAT_ID:
            print(
                "[!] Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set.\n"
                "    Please set them as environment variables, in GitHub Secrets, or in a local .env file.",
                file=sys.stderr
            )
            sys.exit(1)
        
    if args.test:
        latest = items[-1]
        print(f"[*] Sending test message for: {latest['title']}")
        text = format_telegram_message(latest, is_test=True)
        ok = send_telegram_message(BOT_TOKEN, CHAT_ID, text, latest["download_url"], latest["type"])
        if ok:
            print("[+] Test message sent successfully!")
        else:
            print("[-] Failed to send test message.")
        return
        
    if args.check_only:
        for idx, it in enumerate(items, 1):
            print(f"\n[{idx}] {it['title']}")
            print(f"    Type: {it['type']}")
            print(f"    Version: {it['version']}")
            print(f"    MD5: {it['md5']}")
            print(f"    Release (UTC): {it['release_date']}")
            print(f"    Download: {it['download_url']}")
        return

    known_data = load_known_updates()
    known_md5s = set(known_data.get("known_md5s", []))
    is_initial_run = len(known_md5s) == 0
    
    new_items = [it for it in items if it["md5"] and it["md5"] not in known_md5s]
    
    if is_initial_run:
        print("[*] First run detected: Initializing storage with current updates.")
        latest = items[-1]
        welcome_text = (
            "🎉 <b>POCO X8 Pro (klee) Update Tracker Activated!</b>\n\n"
            "You will receive instant alerts whenever a new official <b>Global Fastboot</b> or <b>Recovery</b> update is released.\n\n"
            "📌 <b>Current Latest Global Build:</b>\n"
            f"• <b>ROM Type:</b> <b>{latest['type']}</b>\n"
            f"• <b>Version:</b> <code>{latest['version']}</code>\n"
            f"• <b>MD5 Checksum:</b> <code>{latest['md5']}</code>\n"
            f"• <b>Release Date:</b> <code>{latest['release_date']}</code>"
        )
        print("[*] Sending welcome activation notification...")
        send_telegram_message(BOT_TOKEN, CHAT_ID, welcome_text, latest["download_url"], latest["type"])
        
        for it in items:
            if it["md5"]:
                known_md5s.add(it["md5"])
        known_data["known_md5s"] = list(known_md5s)
        known_data["last_check"] = datetime.now(timezone.utc).isoformat()
        save_known_updates(known_data)
        print(f"[+] Initialized storage with {len(known_md5s)} known ROMs.")
        return
        
    if not new_items and not args.force_notify:
        print("[*] No new Global updates found. Everything is up to date.")
        known_data["last_check"] = datetime.now(timezone.utc).isoformat()
        save_known_updates(known_data)
        return
        
    items_to_send = items if args.force_notify else new_items
    print(f"[+] Found {len(items_to_send)} update(s) to notify!")
    
    for item in items_to_send:
        print(f"[*] Sending alert for: {item['type']} update {item['version']} (MD5: {item['md5']})")
        msg = format_telegram_message(item, is_test=False)
        success = send_telegram_message(BOT_TOKEN, CHAT_ID, msg, item["download_url"], item["type"])
        if success:
            print(f"[+] Notification sent for {item['type']} - {item['version']}")
            known_md5s.add(item["md5"])
        else:
            print(f"[!] Failed to send notification for {item['version']}", file=sys.stderr)
            
    known_data["known_md5s"] = list(known_md5s)
    known_data["last_check"] = datetime.now(timezone.utc).isoformat()
    save_known_updates(known_data)
    print("[+] Done!")

if __name__ == "__main__":
    main()
