import mimetypes
import os
import time
from pathlib import Path
from tkinter import Tk
from tkinter.messagebox import askyesno
top = Tk()
dir_path_str = Path(top.clipboard_get())
top.withdraw()
top.update()
if not dir_path_str.is_dir():
    quit()

to_deletes = []
for path in dir_path_str.glob('**/*'):
    mime = mimetypes.guess_type(path)
    print(path, mime)
    if mime and mime[0] and mime[0].startswith('video'):
        to_deletes.append(path)
to_deletes.sort(key=lambda i: i.as_posix())
for x, path in enumerate(to_deletes, 1):
    path_str = str(path.absolute())
    print(f'{x} / {len(to_deletes)}', path_str)
    os.startfile(path_str)
    time.sleep(1)
    if askyesno(f'{x} / {len(to_deletes)} Delete?', path.name):
        print('deleting', path.as_posix(), path.unlink())
