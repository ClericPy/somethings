import os
import time
import traceback
from pathlib import Path

from morebuiltins.utils import get_paste


def beep():
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    frequency = 800
    duration = 200
    for _ in range(3):
        kernel32.Beep(frequency, duration)


try:
    downloads_path = None
    code = os.system("ffmpeg -version")
    if code != 0:
        raise RuntimeError("ffmpeg not found!")
    url = str(get_paste())
    if url.startswith("http"):
        downloads_path = Path(r"D:/downloads") / f"{Path(url).stem}.mp4"
        cmd = f'ffmpeg.exe -i "{url}" {downloads_path.resolve()}'
        print("download start", downloads_path.resolve())
        for _ in range(3):
            print(3 - _, flush=True)
            time.sleep(1)
        os.system(cmd)
except Exception:
    traceback.print_exc()
finally:
    beep()
    if downloads_path and downloads_path.is_file():
        print("download finished", downloads_path.resolve())
        os.startfile("D:/downloads")
    os.system("pause")
