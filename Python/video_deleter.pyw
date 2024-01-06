import atexit
import mimetypes
import os
import shutil
import time
from pathlib import Path
from queue import Queue
from threading import Thread, Timer
from tkinter import Button, Label, StringVar, Tk

output_dir = Path(r'F:\aaaa\target')
moving = 0
output_q = Queue()


def get_doing():
    return len([1 for i in output_q.queue if i[0]]) + moving


def set_proc():
    if index < len(to_deletes):
        root.title('Moving: %s' % get_doing())
        path: Path = to_deletes[index]
        current_name.set(path.name)
        proc.set(
            f'{index+1} / {len(to_deletes) or "-"} - {round(path.stat().st_size / 1024**2, 1)}MB'
        )
        os.startfile(str(path.absolute()))
    else:
        output_q.put((None, None))
        # task.join()
        # quit()


def aaa():
    global index
    tp = output_dir / 'A'
    tp.mkdir(parents=True, exist_ok=True)
    path: Path = to_deletes[index]
    index += 1
    # path.rename(tp / path.name)
    # Thread(target=shutil.move,
    #        args=(path.as_posix(), (tp / path.name).as_posix())).start()
    output_q.put((path.as_posix(), (tp / path.name).as_posix()))
    set_proc()


def bbb():
    global index
    tp = output_dir / 'B'
    tp.mkdir(parents=True, exist_ok=True)
    path: Path = to_deletes[index]
    index += 1
    # path.rename(tp / path.name)
    # Thread(target=shutil.move,
    #        args=(path.as_posix(), (tp / path.name).as_posix())).start()
    output_q.put((path.as_posix(), (tp / path.name).as_posix()))
    set_proc()


def ccc():
    global index
    tp = output_dir / 'C'
    tp.mkdir(parents=True, exist_ok=True)
    path: Path = to_deletes[index]
    index += 1
    # path.rename(tp / path.name)
    # Thread(target=shutil.move,
    #        args=(path.as_posix(), (tp / path.name).as_posix())).start()
    output_q.put((path.as_posix(), (tp / path.name).as_posix()))
    set_proc()


def eee():
    global index
    tp = output_dir / 'E'
    tp.mkdir(parents=True, exist_ok=True)
    path: Path = to_deletes[index]
    index += 1
    # path.rename(tp / path.name)
    # Thread(target=shutil.move,
    #        args=(path.as_posix(), (tp / path.name).as_posix())).start()
    output_q.put((path.as_posix(), (tp / path.name).as_posix()))
    set_proc()



def fff():
    global index
    index += 1
    # path.rename(tp / path.name)
    # Thread(target=shutil.move,
    #        args=(path.as_posix(), (tp / path.name).as_posix())).start()
    set_proc()

def ddd():
    global index
    tp = output_dir / 'D'
    tp.mkdir(parents=True, exist_ok=True)
    path: Path = to_deletes[index]
    index += 1
    # path.rename(tp / path.name)
    Timer(2, path.unlink).start()
    # Thread(target=shutil.move,
    #        args=(path.as_posix(), (tp / path.name).as_posix())).start()
    set_proc()


def deliver():
    global moving
    while True:
        a, b = output_q.get()
        if a is None:
            break
        root.title('Moving: %s' % get_doing())
        moving = 1
        shutil.move(a, b)
        moving = 0
        root.title('Moving: %s' % get_doing())
    root.destroy()


index = 0
to_deletes = []
root = Tk()
proc = StringVar()
current_name = StringVar()
root.title('Choose a folder')
root.geometry('310x200+900+600')
proc_l = Label(root, textvariable=proc, width=40, background='white')
proc_l.grid(row=0, columnspan=2)
label1 = Label(root, textvariable=current_name, width=40, background='white')
label1.grid(row=1, columnspan=2)
Button(root, text='aaa', command=aaa, width=20, height=2).grid(column=0, row=2)
Button(root, text='bbb', command=bbb, width=20, height=2).grid(column=1, row=2)
Button(root, text='ccc', command=ccc, width=20, height=2).grid(column=0, row=3)
Button(root, text='fff', command=fff, width=20, height=2).grid(column=1, row=3)
Button(root, text='ddd', command=ddd, width=20, height=2).grid(column=1, row=4)
Button(root, text='eee', command=eee, width=20, height=2).grid(column=0, row=4)
root.attributes('-topmost', True)
root.update()
task = Thread(target=deliver)
task.start()
while True:
    dir_path_str = Path(root.clipboard_get())
    if dir_path_str.is_dir():
        for path in dir_path_str.glob('**/*'):
            mime = mimetypes.guess_type(path)
            # print(path, mime)
            if mime and mime[0] and mime[0].startswith('video'):
                to_deletes.append(path)
        # to_deletes.sort(key=lambda i: i.stat().st_ctime)
        to_deletes.sort(key=lambda i: i.stat().st_size, reverse=True)
        # to_deletes.sort(key=lambda i: i.stat().st_size, reverse=True)
        set_proc()
        break
    else:
        time.sleep(1)
try:
    root.mainloop()
finally:
    output_q.put((None, None))
    task.join()
