#! ../.venv/Scripts/pythonw.exe
"""
This is a simple tray RSS subscription reminder management software. Single-file script, no dependencies on other files.
1. Feature Overview:
- Supports adding, deleting, and managing RSS feed sources.
- Periodically checks feed updates, and notifies users of new content by changing the unread count in the system tray.
- Supports custom check interval time.
- Provides a simple user interface: web UI.
- When clicking the tray icon, opens the web UI to view and manage subscription content. Unread content is highlighted.
- Saves all unread content, or content within seven days, for easy user access.

2. Tech Stack:
- Python 3.13+
- Uses feedparser library to parse RSS feeds.
- Web content is not from actual HTML files, but generated in memory.
- Uses diskcache library for local cache storage.
- Uses pystray library to implement system tray icon and menu.
"""

import hashlib
import json
import logging
import os
import socket
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

# Check dependencies
try:
    import diskcache
    import feedparser
    import pystray
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    time.sleep(5)
    sys.exit(1)

sys.stdout = open(os.devnull, "w")
sys.stderr = open(os.devnull, "w")

# Configuration
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".simple_rss_cache")
RETENTION_DAYS = 7

# Initialize Cache
cache = diskcache.Cache(CACHE_DIR)


def get_config():
    config = cache.get("config:settings", {})
    updated = False
    if "port" not in config:
        # Find free port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("localhost", 0))
        port = sock.getsockname()[1]
        sock.close()
        config["port"] = port
        updated = True
    if "check_interval" not in config:
        config["check_interval"] = 120
        updated = True
    if updated:
        cache["config:settings"] = config
    return config


# Load runtime configuration
current_config = get_config()
PORT = current_config["port"]
CHECK_INTERVAL = current_config["check_interval"]

# Global State
state = {"unread_count": 0, "icon": None, "running": True}


def get_feeds():
    return cache.get("config:feeds", [])


def add_feed(url):
    feeds = get_feeds()
    if url not in feeds:
        feeds.append(url)
        cache["config:feeds"] = feeds
        return True
    return False


def remove_feed(url):
    feeds = get_feeds()
    if url in feeds:
        feeds.remove(url)
        cache["config:feeds"] = feeds
        return True
    return False


def get_entry_id(entry):
    # Prefer id, fallback to link, fallback to title+date
    return entry.get("id", entry.get("link", entry.get("title", "")))


def parse_date(entry):
    if "published_parsed" in entry and entry.published_parsed:
        return datetime.fromtimestamp(time.mktime(entry.published_parsed))
    return datetime.now()


def update_feeds():
    feeds = get_feeds()
    new_items_count = 0

    for url in feeds:
        try:
            d = feedparser.parse(url)
            feed_title = d.feed.get("title", url)

            for entry in d.entries:
                eid = get_entry_id(entry)
                # Create a deterministic hash for the ID to use as cache key
                key_hash = hashlib.md5(eid.encode("utf-8", errors="ignore")).hexdigest()
                cache_key = f"entry:{key_hash}"

                if cache_key not in cache:
                    # New entry
                    dt = parse_date(entry)
                    summary = entry.get("summary", "")
                    # Basic HTML stripping could be done here, but keeping it simple

                    data = {
                        "id": eid,
                        "title": entry.get("title", "No Title"),
                        "link": entry.get("link", ""),
                        "summary": summary,
                        "published": dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "timestamp": dt.timestamp(),
                        "feed_title": feed_title,
                        "is_read": False,
                        "key": cache_key,
                    }
                    cache[cache_key] = data
                    new_items_count += 1
        except Exception as e:
            logging.error(f"Failed to parse {url}: {e}")

    cleanup_entries()
    update_unread_count()
    update_tray_icon()


def cleanup_entries():
    # Remove read entries older than RETENTION_DAYS
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    cutoff_ts = cutoff.timestamp()

    keys_to_delete = []
    for key in cache.iterkeys():
        if key.startswith("entry:"):
            data = cache[key]
            if data["is_read"] and data["timestamp"] < cutoff_ts:
                keys_to_delete.append(key)

    for key in keys_to_delete:
        del cache[key]


def update_unread_count():
    count = 0
    for key in cache.iterkeys():
        if key.startswith("entry:"):
            if not cache[key]["is_read"]:
                count += 1
    state["unread_count"] = count


def create_image(count):
    # Generate an icon with the unread count
    width = 64
    height = 64
    color = (66, 133, 244) if count > 0 else (128, 128, 128)

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)

    # Draw circle
    dc.ellipse((4, 4, 60, 60), fill=color)

    # Draw text
    text = str(count) if count < 99 else "99+"
    try:
        # Try to load a default font, otherwise use default
        font = ImageFont.truetype("arial.ttf", 30)
    except IOError:
        font = ImageFont.load_default()

    # Calculate text position (centering)
    try:
        left, top, right, bottom = dc.textbbox((0, 0), text, font=font)
        w = right - left
        h = bottom - top
    except AttributeError:
        w, h = dc.textsize(text, font=font)

    dc.text(
        ((width - w) / 2, (height - h) / 2 - 2), text, font=font, fill=(255, 255, 255)
    )

    return image


def update_tray_icon():
    if state["icon"]:
        state["icon"].icon = create_image(state["unread_count"])
        state["icon"].title = f"Simple RSS: {state['unread_count']} unread"


# --- Web Server ---


def set_readed(now_ts):
    keys = [k for k in cache.iterkeys() if k.startswith("entry:")]
    changed = False
    for key in keys:
        try:
            entry = cache[key]
            if not entry["is_read"] and entry["timestamp"] <= now_ts:
                entry["is_read"] = True
                cache[key] = entry
                changed = True
        except Exception:
            pass
    if changed:
        update_unread_count()
        update_tray_icon()


class RSSRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            # Auto mark unread entries as read if published before now
            threading.Timer(10, set_readed, args=(time.time(),)).start()
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.generate_html().encode("utf-8"))
        else:
            self.send_error(404)

    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode("utf-8"))

        if self.path == "/api/add_feed":
            add_feed(data.get("url"))
            threading.Thread(target=update_feeds).start()  # Trigger update
        elif self.path == "/api/delete_feed":
            remove_feed(data.get("url"))
        elif self.path == "/api/mark_read":
            key = data.get("key")
            if key in cache:
                entry = cache[key]
                entry["is_read"] = True
                cache[key] = entry
                update_unread_count()
                update_tray_icon()
        elif self.path == "/api/mark_all_read":
            for key in cache.iterkeys():
                if key.startswith("entry:"):
                    entry = cache[key]
                    if not entry["is_read"]:
                        entry["is_read"] = True
                        cache[key] = entry
            update_unread_count()
            update_tray_icon()
        elif self.path == "/api/refresh":
            threading.Thread(target=update_feeds).start()
        elif self.path == "/api/save_settings":
            try:
                new_port = int(data.get("port"))
                new_interval = int(data.get("interval"))
                config = cache.get("config:settings", {})
                config["port"] = new_port
                config["check_interval"] = new_interval
                cache["config:settings"] = config
            except ValueError:
                pass

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def generate_html(self):
        feeds = get_feeds()
        config = get_config()
        current_port = config.get("port", PORT)
        current_interval = config.get("check_interval", CHECK_INTERVAL)

        entries = []
        for key in cache.iterkeys():
            if key.startswith("entry:"):
                entries.append(cache[key])

        # Sort: Unread first, then by date desc
        entries.sort(key=lambda x: (x["is_read"], -x["timestamp"]))

        feed_list_html = "".join(
            [
                f'<div class="feed-item"><span>{url}</span> <button onclick="deleteFeed(\'{url}\')">Delete</button></div>'
                for url in feeds
            ]
        )

        settings_html = f"""
        <div class="control-panel">
            <h2>Settings</h2>
            <div style="display: flex; gap: 10px; align-items: center;">
                <label>Port: <input type="number" id="portInput" value="{current_port}" style="width: 80px;"></label>
                <label>Interval (s): <input type="number" id="intervalInput" value="{current_interval}" style="width: 80px;"></label>
                <button onclick="saveSettings()">Save</button>
            </div>
            <small style="color: #666;">Note: Changing port requires application restart.</small>
        </div>
        """

        entries_html = ""
        for e in entries:
            status_class = "read" if e["is_read"] else "unread"
            check_mark = '<span class="checkmark">√</span>' if e["is_read"] else ""
            # Simple summary truncation
            summary = (
                e["summary"][:300] + "..." if len(e["summary"]) > 300 else e["summary"]
            )
            # Remove HTML tags from summary for safety/cleanliness (optional, doing basic replace)
            summary = summary.replace("<", "&lt;").replace(">", "&gt;")

            entries_html += f"""
            <div class="entry {status_class}" id="{e["key"]}">
                <div class="entry-header">
                    {check_mark}
                    <span class="feed-title">{e["feed_title"]}</span>
                    <span class="date">{e["published"]}</span>
                </div>
                <h3><a href="{e["link"]}" target="_blank" onclick="markRead('{e["key"]}')">{e["title"]}</a></h3>
                <div class="summary">{summary}</div>
                <div class="actions">
                    {"<button onclick=\"markRead('" + e["key"] + "')\">Mark Read</button>" if not e["is_read"] else "<span>Read</span>"}
                </div>
            </div>
            """

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Simple RSS</title>
    <style>
        body {{ font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f0f2f5; }}
        .control-panel {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .feed-item {{ display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #eee; }}
        .entry {{ background: white; padding: 15px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid transparent; }}
        .entry.unread {{ border-left-color: #4285f4; }}
        .entry.read {{ opacity: 0.7; }}
        .entry-header {{ font-size: 0.8em; color: #666; display: flex; justify-content: space-between; }}
        h3 {{ margin: 5px 0; }}
        a {{ text-decoration: none; color: #333; }}
        a:hover {{ color: #4285f4; }}
        .summary {{ font-size: 0.9em; color: #444; margin-top: 5px; }}
        .actions {{ margin-top: 10px; text-align: right; }}
        button {{ cursor: pointer; padding: 5px 10px; background: #eee; border: none; border-radius: 4px; }}
        button:hover {{ background: #ddd; }}
        input {{ padding: 5px; width: 70%; }}
        .checkmark {{ color: #34a853; margin-left: 8px; font-weight: bold; }}
    </style>
    <script>
        function api(endpoint, data) {{
            fetch('/api/' + endpoint, {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify(data)
            }}).then(() => {{
                if (endpoint === 'save_settings') {{
                    alert('Settings saved. If port changed, please restart application.');
                }}
                location.reload();
            }});
        }}
        function toggleFeeds() {{
            const list = document.getElementById('feedList');
            const btn = document.getElementById('toggleFeedsBtn');
            if (list.style.display === 'none') {{
                list.style.display = 'block';
                btn.innerText = 'Hide List';
            }} else {{
                list.style.display = 'none';
                btn.innerText = 'Show List';
            }}
        }}
        function addFeed() {{
            const url = document.getElementById('urlInput').value;
            if(url) api('add_feed', {{url: url}});
        }}
        function saveSettings() {{
            const port = document.getElementById('portInput').value;
            const interval = document.getElementById('intervalInput').value;
            api('save_settings', {{port: port, interval: interval}});
        }}
        function deleteFeed(url) {{
            if(confirm('Delete ' + url + '?')) api('delete_feed', {{url: url}});
        }}
        function markRead(key) {{
            api('mark_read', {{key: key}});
        }}
        function markAllRead() {{
            api('mark_all_read', {{}});
        }}
        function refresh() {{
            api('refresh', {{}});
        }}
    </script>
</head>
<body>
    {settings_html}
    <div class="control-panel">
        <h2>{len(feeds)} Feeds<button id="toggleFeedsBtn" onclick="toggleFeeds()" style="font-size: 0.6em; vertical-align: middle;">Show List</button></h2>
        <input type="text" id="urlInput" placeholder="RSS URL">
        <button onclick="addFeed()">Add</button>
        <button onclick="refresh()">Check Now</button>
        <div id="feedList" style="margin-top: 10px; display: none;">
            {feed_list_html}
        </div>
    </div>
    
    <div class="control-panel" style="display: flex; justify-content: space-between; align-items: center;">
        <h2>Entries ({state["unread_count"]} unread)</h2>
        <button onclick="markAllRead()">Mark All Read</button>
    </div>
    
    <div>
        {entries_html}
    </div>
</body>
</html>
"""


def run_server():
    server = HTTPServer(("localhost", PORT), RSSRequestHandler)
    server.serve_forever()


def background_worker():
    while state["running"]:
        update_feeds()
        # Reload config to get latest interval
        cfg = get_config()
        interval = cfg.get("check_interval", 120)
        time.sleep(interval)


def on_tray_action(icon, item):
    if str(item) == "Open Web UI":
        webbrowser.open(f"http://localhost:{PORT}")
    elif str(item) == "Check Now":
        threading.Thread(target=update_feeds).start()
    elif str(item) == "Exit":
        state["running"] = False
        icon.stop()
        os._exit(0)


def main():
    # Start Web Server
    threading.Thread(target=run_server, daemon=True).start()

    # Start Background Worker
    threading.Thread(target=background_worker, daemon=True).start()

    # Initial update
    update_unread_count()

    # Tray Icon
    menu = pystray.Menu(
        pystray.MenuItem("Open Web UI", on_tray_action, default=True),
        pystray.MenuItem("Check Now", on_tray_action),
        pystray.MenuItem("Exit", on_tray_action),
    )

    state["icon"] = pystray.Icon("SimpleRSS", create_image(0), "Simple RSS", menu)
    state["icon"].run()


if __name__ == "__main__":
    main()
