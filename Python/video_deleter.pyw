import mimetypes
import os
from pathlib import Path
from tkinter import Tk, Label, Button, StringVar


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


def yes():
    global index
    path: Path = to_deletes[index]
    index += 1
    path.rename(yes_path / path.name)
    set_proc()


def no():
    global index
    path: Path = to_deletes[index]
    index += 1
    path.rename(no_path / path.name)
    set_proc()


index = 0
to_deletes = []
root = Tk()
proc = StringVar()
current_name = StringVar()
root.title('Choose a folder')
root.geometry('400x100+0+0')
proc_l = Label(root, textvariable=proc, width=40, background='white')
proc_l.grid(row=0, columnspan=2)
label1 = Label(root, textvariable=current_name, width=40, background='white')
label1.grid(row=1, columnspan=2)
btn1 = Button(root, text='Yes', command=yes, width=20)
btn2 = Button(root, text='No', command=no, width=20)
root.attributes('-topmost', True)
root.update()
dir_path_str = Path(root.clipboard_get())
# print('dir_path_str:', dir_path_str)
if dir_path_str.is_dir():
    yes_path = dir_path_str / '__yes'
    yes_path.mkdir(parents=True, exist_ok=True)
    no_path = dir_path_str / '__no'
    no_path.mkdir(parents=True, exist_ok=True)
    for path in dir_path_str.glob('**/*'):
        if path.parent.name.startswith('__'):
            continue
        mime = mimetypes.guess_type(path)
        # print(path, mime)
        if mime and mime[0] and mime[0].startswith('video'):
            to_deletes.append(path)
    to_deletes.sort(key=lambda i: i.stat().st_ctime)
    to_deletes.sort(key=lambda i: i.stat().st_size, reverse=True)
    btn1.grid(column=0, row=2)
    btn2.grid(column=1, row=2)
    set_proc()
else:
    quit()
root.mainloop()
