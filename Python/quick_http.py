import os
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, test
from pathlib import Path
from threading import Timer


def get_paste():
    from tkinter import TclError, Tk

    text = _tk = None
    try:
        _tk = Tk()
        _tk.withdraw()
        text = _tk.clipboard_get()
    except TclError:
        raise
    finally:
        if _tk:
            _tk.destroy()
        return text


path = Path(get_paste())
if path.is_dir():
    from win_my_lan import find_ip

    lan_ip = find_ip().get("IPv4")
    if not lan_ip:
        print("No lan ip found", flush=True)
        time.sleep(3)
    port = 8000
    url = f"http://{lan_ip}:{port}"
    print(url, flush=True)
    os.chdir(path)
    Timer(0.5, webbrowser.open, args=(url,)).start()
    test(SimpleHTTPRequestHandler, bind=lan_ip, port=port)
