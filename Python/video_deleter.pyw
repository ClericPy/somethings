import mimetypes
import os
from pathlib import Path
from tkinter import Tk, Label, Button, StringVar

# for x, path in enumerate(to_deletes, 1):
#     path_str = str(path.absolute())
#     print(f'{x} / {len(to_deletes)}', path_str)
#     os.startfile(path_str)
#     time.sleep(1)
#     if askyesno(f'{x} / {len(to_deletes)} Delete?', path.name):
#         print('deleting', path.as_posix(), path.unlink())


def set_proc():
    global index
    if index < len(to_deletes):
        path = to_deletes[index - 1]
        current_name.set(path.name)
        index += 1
        proc.set(f'{index} / {len(to_deletes) or "-"}')
        os.startfile(str(path.absolute()))
    else:
        quit()


def delete():
    path = to_deletes[index - 2]
    if path.is_file():
        path.unlink()
        # print('delete', path)
    set_proc()


def ignore():
    set_proc()


index = 0
to_deletes = []
root = Tk()
proc = StringVar()
current_name = StringVar()
root.title('Delete this video?')
root.geometry('400x100+0+0')
proc_l = Label(root, textvariable=proc, width=40, background='white')
proc_l.grid(row=0, columnspan=2)
label1 = Label(root, textvariable=current_name, width=40, background='white')
label1.grid(row=1, columnspan=2)
btn1 = Button(root, text='Delete', command=delete, width=20)
btn2 = Button(root, text='Ignore', command=ignore, width=20)
root.attributes('-topmost', True)
root.update()
dir_path_str = Path(root.clipboard_get())
# print('dir_path_str:', dir_path_str)
if dir_path_str.is_dir():
    for path in dir_path_str.glob('**/*'):
        mime = mimetypes.guess_type(path)
        # print(path, mime)
        if mime and mime[0] and mime[0].startswith('video'):
            to_deletes.append(path)
    to_deletes.sort(key=lambda i: i.stat().st_ctime)
    set_proc()
    btn1.grid(column=0, row=2)
    btn2.grid(column=1, row=2)
else:
    quit()
root.mainloop()
