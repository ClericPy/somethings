import os
import re
import subprocess
import time
import traceback
from pathlib import Path

from morebuiltins.request import req
from morebuiltins.utils import get_paste


def beep():
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    frequency = 1000
    duration = 300
    for _ in range(3):
        kernel32.Beep(frequency, duration)


try:
    ok = False
    downloads_path = None
    code = os.system("ffmpeg -version")
    if code != 0:
        raise RuntimeError("ffmpeg not found!")
    url = str(get_paste()).strip()
    if url.startswith("http"):
        text = req.get(url, headers={"user-agent": ""}).text
        total_time_secs = sum(
            [float(i) for i in re.findall(r"EXTINF:(\d+\.?\d*),", text)]
        )
        if total_time_secs > 3600:
            total_time = f"{round(total_time_secs / 3600, 1)} hours"
        else:
            total_time = f"{round(total_time_secs / 60, 1)} mins"
        downloads_path = Path(r"D:/downloads") / f"{Path(url).stem}-{time.strftime('%Y%m%d%H%M%S')}.mp4"
        # cmd = ["ffmpeg.exe", "-i", url, downloads_path.resolve()]
        # -socks5-proxy socks5://ip:port
        # -http_proxy http://127.0.0.1:1080
        # proxy = " -http_proxy http://127.0.0.1:1080"
        proxy = ""
        cmd = f'ffmpeg.exe {proxy} -y -i "{url}" {downloads_path.resolve()}'
        print(f"[{total_time}]", "download start", downloads_path.resolve(), flush=True)
        p = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            # env={'HTTP_PROXY': 'http://127.0.0.1:1080', 'HTTPS_PROXY': 'http://127.0.0.1:1080'},
            encoding="utf-8",
            errors="replace",
        )
        perc = "    "
        for line in p.stdout or []:
            # time=00:00:26.09
            m = re.search(r"time=((\d+):(\d+):(\d+))", line)
            if m:
                done = m[1]
                perc = "%s%%" % (
                    round(
                        100
                        * (int(m[2]) * 3600 + int(m[3]) * 60 + int(m[4]))
                        / total_time_secs,
                    )
                )
            else:
                done = "        "
            print(f"[{total_time}]", done, "|", perc, "|", line.rstrip(), flush=True)
        ok = True
except Exception:
    traceback.print_exc()
finally:
    if downloads_path and downloads_path.is_file():
        if ok:
            new_name = input("new name:")
            if new_name:
                downloads_path.rename(downloads_path.with_stem(new_name))
            print("download finished", downloads_path.resolve())
            os.startfile("D:/downloads")
        else:
            downloads_path.unlink(missing_ok=True)
    beep()
    os.system("pause")
