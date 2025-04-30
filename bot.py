import os
import time
import subprocess
import requests
import asyncio
import xmlrpc.client
from telethon import TelegramClient, events
from telethon.tl.types import InputFile
from datetime import timedelta

# === Bot Credentials ===
api_id = 22716138
api_hash = '24aa97b83dc56cbde6cb572dbfa6feca'
bot_token = '8001013935:AAGH94E1VSU4efp6GnjC6h2SfV5OHhG4ejU'

# === Initialize Bot ===
bot = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)
print("[STARTED] Terabox Downloader Bot is running...")

ARIA2C_SECRET = "token"
ARIA2C_RPC = "http://localhost:6800/rpc"

async def download_with_progress(url, filename, msg):
    # Start aria2c with RPC
    subprocess.Popen([
        "aria2c", "--enable-rpc", "--rpc-listen-all=false", "--rpc-allow-origin-all",
        f"--rpc-secret={ARIA2C_SECRET}", "--dir=.", "-o", filename, url
    ])
    time.sleep(1)  # Wait for aria2c to start

    # Connect to aria2c RPC
    server = xmlrpc.client.ServerProxy(ARIA2C_RPC)
    gid = server.aria2.tellActive(f"token:{ARIA2C_SECRET}")[0]['gid']

    last_percent = -1
    while True:
        try:
            status = server.aria2.tellStatus(f"token:{ARIA2C_SECRET}", gid, ['completedLength', 'totalLength', 'status'])
            total = int(status['totalLength'])
            completed = int(status['completedLength'])
            percent = int((completed / total) * 100) if total > 0 else 0
            if percent != last_percent:
                await msg.edit(f"⏬ Downloading: `{percent}%`")
                last_percent = percent
            if status['status'] == 'complete':
                break
        except Exception:
            break
        await asyncio.sleep(1)

async def upload_with_progress(event, filepath, caption, thumb_path):
    file_size = os.path.getsize(filepath)
    sent_msg = await event.respond("📤 Uploading: `0%`")

    async def progress(current, total):
        percent = int(current * 100 / total)
        await sent_msg.edit(f"📤 Uploading: `{percent}%`")

    await bot.send_file(
        event.chat_id,
        filepath,
        caption=caption,
        thumb=thumb_path if os.path.exists(thumb_path) else None,
        supports_streaming=True,
        progress_callback=progress
    )
    await sent_msg.delete()

@bot.on(events.NewMessage(pattern=r'https://terabox.com/s/\S+'))
async def handle_terabox(event):
    try:
        url = event.raw_text.strip()
        status_msg = await event.respond("🔄 Getting file info...")

        meta_response = requests.post(
            "https://teradl-api.dapuntaratya.com/generate_file",
            headers={"Content-Type": "application/json"},
            json={"url": url}
        )
        meta_data = meta_response.json()
        if meta_data.get("status") != "success":
            await status_msg.edit("❌ Failed to fetch metadata.")
            return

        file_info = meta_data["list"][0]
        name = file_info["name"]

        stream_data = {
            "sign": meta_data["sign"],
            "timestamp": meta_data["timestamp"],
            "shareid": meta_data["shareid"],
            "uk": meta_data["uk"],
            "fs_id": file_info["fs_id"]
        }

        video_res = requests.post("https://teradl-api.dapuntaratya.com/generate_link", json=stream_data)
        video_json = video_res.json()
        video_url = video_json.get("download_link", {}).get("url_2")

        if not video_url:
            await status_msg.edit("❌ Couldn't fetch video link.")
            return

        # Download with progress
        await download_with_progress(video_url, name, status_msg)

        # Extract thumbnail and duration
        duration = "N/A"
        thumb_path = "thumb.jpg"
        try:
            ffprobe_cmd = [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                name
            ]
            duration_sec = float(subprocess.check_output(ffprobe_cmd).strip())
            duration = str(timedelta(seconds=int(duration_sec)))

            subprocess.run([
                "ffmpeg", "-ss", "00:00:01", "-i", name,
                "-frames:v", "1", "-q:v", "2", thumb_path
            ], check=True)
        except Exception as e:
            print(f"[ERROR] Thumbnail extraction: {e}")
            thumb_path = None

        # Upload with progress
        caption = f"🎥 `{name}`\n⏱ Duration: `{duration}`\n\nDownloaded by @automatedworld"
        await upload_with_progress(event, name, caption, thumb_path)

        # Clean up
        os.remove(name)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)

    except Exception as e:
        print(f"[ERROR] {e}")
        await event.respond(f"❌ Error occurred: {e}")

bot.run_until_disconnected()
