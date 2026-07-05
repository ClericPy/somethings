"""
Windows Audio Output Switcher
Pure stdlib + PowerShell AudioDeviceCmdlets, instant startup via cache.

Dependency:
  - AudioDeviceCmdlets PowerShell module:
      Install-Module -Name AudioDeviceCmdlets -Scope CurrentUser

Usage:
  .venv/Scripts/python audio_switch.py
"""

import tkinter as tk
import subprocess
import threading
import json
import os
import time


CACHE_FILE = os.path.join(os.environ.get('TEMP', ''), 'audio_switch_cache.json')


def ps_run(cmd: str) -> tuple:
    """Run PowerShell command, return (returncode, stdout, stderr)"""
    p = subprocess.Popen(
        ['powershell', '-NoProfile', '-Command', cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = p.communicate()
    return (
        p.returncode,
        out.decode('gbk', errors='replace'),
        err.decode('gbk', errors='replace'),
    )


def ps_fire(cmd: str):
    """Fire and forget: launch PowerShell, don't wait"""
    subprocess.Popen(
        ['powershell', '-NoProfile', '-Command', cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def load_cache():
    """Try to load cache, return (devices, default_id) or None"""
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['devices'], data['default_id']
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


def save_cache(devices, default_id):
    """Write cache file"""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'ts': time.time(),
                'devices': devices,
                'default_id': default_id,
            }, f, ensure_ascii=False)
    except OSError:
        pass


def fetch_devices_slow():
    """Slow query: enumerate all playback devices + current default"""
    cmd = (
        "Get-AudioDevice -List "
        "| Where-Object { $_.Type -eq 'Playback' } "
        '| ForEach-Object { "$($_.ID)|$($_.Name)" }; '
        "; "
        "(Get-AudioDevice -Playback).ID"
    )
    rc, out, err = ps_run(cmd)
    if rc != 0:
        return None

    lines = [line.strip() for line in out.strip().splitlines() if line.strip()]
    default_id = ''
    devices = []
    for line in lines:
        if '|' in line:
            dev_id, name = line.split('|', 1)
            devices.append([name.strip(), dev_id.strip()])
        else:
            default_id = line.strip()

    devices.sort(key=lambda x: x[0])
    return devices, default_id


# --- Styles ---
BG = "#2b2b2b"
FG = "#e0e0e0"
BTN_BG = "#3c3c3c"
BTN_ACTIVE = "#505050"
BTN_CURRENT = "#2a5a2a"
BTN_REFRESH = "#3a5a7a"   # distinct color for refresh button
FONT = ("Segoe UI", 11)
FONT_SMALL = ("Segoe UI", 9)


def main():
    root = tk.Tk()
    root.title("Audio Output")
    root.resizable(False, False)
    root.configure(bg=BG)

    tk.Label(
        root, text="Select audio output device", font=FONT,
        bg=BG, fg="#ffffff", pady=12,
    ).pack(fill=tk.X)

    btn_frame = tk.Frame(root, bg=BG, padx=16, pady=4)
    btn_frame.pack(fill=tk.BOTH, expand=True)

    # Container for device buttons
    device_frame = tk.Frame(btn_frame, bg=BG)
    device_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

    # Refresh button
    refresh_btn = tk.Button(
        btn_frame,
        text="⟳  Refresh",
        font=FONT,
        anchor="center",
        relief="flat",
        padx=12,
        pady=6,
        cursor="hand2",
        bg=BTN_REFRESH,
        fg="#ffffff",
        activebackground="#4a6a8a",
        activeforeground="#ffffff",
        bd=0,
        highlightthickness=0,
    )
    refresh_btn.pack(fill=tk.X, pady=(8, 2))

    # Delete cache button
    delete_btn = tk.Button(
        btn_frame,
        text="✕  Delete Cache",
        font=FONT,
        anchor="center",
        relief="flat",
        padx=12,
        pady=6,
        cursor="hand2",
        bg="#5a3a3a",
        fg="#ffffff",
        activebackground="#7a4a4a",
        activeforeground="#ffffff",
        bd=0,
        highlightthickness=0,
    )
    delete_btn.pack(fill=tk.X, pady=(2, 0))

    # Status label
    status = tk.Label(
        root, text="", font=FONT_SMALL,
        bg=BG, fg="#aaaaaa", pady=6,
    )
    status.pack(fill=tk.X)

    # Cache path label at the very bottom
    tk.Label(
        root, text=f"Cache: {CACHE_FILE}", font=("Segoe UI", 8),
        bg=BG, fg="#666666", pady=6,
    ).pack(fill=tk.X, side=tk.BOTTOM)

    # Center window
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"+{x}+{y}")

    # dev_id -> btn
    btn_map = {}
    busy = False

    def delete_cache():
        """Delete cache file directly, no background thread"""
        try:
            os.remove(CACHE_FILE)
            status.configure(text="Cache deleted")
        except FileNotFoundError:
            status.configure(text="No cache file to delete")
        except Exception as e:
            status.configure(text=f"Cannot delete: {e}")

    # Wire delete button
    delete_btn.configure(command=delete_cache)

    def rebuild_buttons(devices, default_id):
        """Rebuild all device buttons"""
        for btn in btn_map.values():
            btn.destroy()
        btn_map.clear()
        for name, dev_id in devices:
            is_current = (dev_id == default_id)
            btn = tk.Button(
                device_frame,
                text=f"  {name}  ",
                font=FONT,
                anchor="w",
                relief="flat",
                padx=12,
                pady=6,
                cursor="hand2",
                bg=BTN_CURRENT if is_current else BTN_BG,
                fg="#ffffff" if is_current else FG,
                activebackground=BTN_CURRENT if is_current else BTN_ACTIVE,
                activeforeground="#ffffff",
                bd=0,
                highlightthickness=0,
            )
            btn.pack(fill=tk.X, pady=2)
            btn.configure(command=lambda d=dev_id, n=name: on_click(d, n))
            btn_map[dev_id] = btn

        root.update_idletasks()
        w2 = root.winfo_width()
        h2 = root.winfo_height()
        x2 = (root.winfo_screenwidth() - w2) // 2
        y2 = (root.winfo_screenheight() - h2) // 2
        root.geometry(f"+{x2}+{y2}")

    def on_click(dev_id, name):
        """Device button clicked: switch, then close GUI"""
        nonlocal busy
        busy = True
        for btn in btn_map.values():
            btn.configure(state='disabled')
        ps_fire(f'Set-AudioDevice -ID "{dev_id}"')
        status.configure(text=f"Switching to {name}...")
        device_frame.after(300, root.destroy)

    def do_refresh():
        """Refresh button clicked: reload device list"""
        nonlocal busy
        if busy:
            return
        busy = True
        refresh_btn.configure(state='disabled')
        status.configure(text="Loading...")

        def worker():
            result = fetch_devices_slow()
            if result:
                devices, default_id = result
                save_cache(devices, default_id)
                root.after(0, lambda: on_refresh_done(devices, default_id, None))
            else:
                root.after(0, lambda: on_refresh_done(None, None, "Load failed"))

        threading.Thread(target=worker, daemon=True).start()

    def on_refresh_done(devices, default_id, error):
        nonlocal busy
        busy = False
        refresh_btn.configure(state='normal')
        if error:
            status.configure(text=error)
            return
        rebuild_buttons(devices, default_id)
        status.configure(text="")

    # Wire refresh button
    refresh_btn.configure(command=do_refresh)

    # Initial load: try cache, else prompt user to click Refresh
    cached = load_cache()
    if cached:
        devices, default_id = cached
        rebuild_buttons(devices, default_id)
    else:
        status.configure(text="No cache found. Click Refresh to load devices.")

    root.mainloop()


if __name__ == "__main__":
    main()
