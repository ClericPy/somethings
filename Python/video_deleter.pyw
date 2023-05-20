import atexit
import mimetypes
import os
import shutil
import time
from pathlib import Path
from tkinter import Button, Label, StringVar, Tk

output_dir = Path(r'F:\aaaa\target')


def shutdown():
    print(index, len(to_deletes))
    # if index == len(to_deletes):
    if (output_dir / 'D').is_dir():
        shutil.rmtree(str(output_dir / 'D'))


def set_proc():
    if index < len(to_deletes):
        path: Path = to_deletes[index]
        current_name.set(path.name)
        proc.set(
            f'{index+1} / {len(to_deletes) or "-"} - {round(path.stat().st_size / 1024**2, 1)}MB'
        )
        os.startfile(str(path.absolute()))
    else:
        quit()


def aaa():
    global index
    aaa_path = output_dir / 'A'
    aaa_path.mkdir(parents=True, exist_ok=True)
    path: Path = to_deletes[index]
    index += 1
    path.rename(aaa_path / path.name)
    set_proc()


def bbb():
    global index
    bbb_path = output_dir / 'B'
    bbb_path.mkdir(parents=True, exist_ok=True)
    path: Path = to_deletes[index]
    index += 1
    path.rename(bbb_path / path.name)
    set_proc()


def ccc():
    global index
    ccc_path = output_dir / 'C'
    ccc_path.mkdir(parents=True, exist_ok=True)
    path: Path = to_deletes[index]
    index += 1
    path.rename(ccc_path / path.name)
    set_proc()


def ddd():
    global index
    ddd_path = output_dir / 'D'
    ddd_path.mkdir(parents=True, exist_ok=True)
    path: Path = to_deletes[index]
    index += 1
    path.rename(ddd_path / path.name)
    set_proc()


atexit.register(shutdown)
index = 0
to_deletes = []
root = Tk()
proc = StringVar()
current_name = StringVar()
root.title('Choose a folder')
root.geometry('310x150+900+600')
proc_l = Label(root, textvariable=proc, width=40, background='white')
proc_l.grid(row=0, columnspan=2)
label1 = Label(root, textvariable=current_name, width=40, background='white')
label1.grid(row=1, columnspan=2)
Button(root, text='aaa', command=aaa, width=20, height=2).grid(column=0, row=2)
Button(root, text='bbb', command=bbb, width=20, height=2).grid(column=1, row=2)
Button(root, text='ccc', command=ccc, width=20, height=2).grid(column=0, row=3)
Button(root, text='ddd', command=ddd, width=20, height=2).grid(column=1, row=3)
root.attributes('-topmost', True)
root.update()

while True:
    dir_path_str = Path(root.clipboard_get())
    if dir_path_str.is_dir():
        for path in dir_path_str.glob('**/*'):
            mime = mimetypes.guess_type(path)
            # print(path, mime)
            if mime and mime[0] and mime[0].startswith('video'):
                to_deletes.append(path)
        to_deletes.sort(key=lambda i: i.stat().st_ctime)
        to_deletes.sort(key=lambda i: i.stat().st_size, reverse=True)
        set_proc()
        break
    else:
        time.sleep(1)
root.mainloop()
