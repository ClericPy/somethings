from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from pathlib import Path
from threading import Lock
from tkinter import Tk

top = Tk()
dir_path_str = top.clipboard_get()
top.withdraw()
top.update()
top.destroy()

lock = Lock()
seen: dict = {}
to_del = []
loop = 1
chech_size = 1 * 1024**2
todos = list(Path(dir_path_str).rglob('*.*'))
pool = ThreadPoolExecutor()
tasks = []


def work(path):
    h = sha256()
    try:
        with open(path, 'rb') as f:
            for _ in range(loop):
                chunk = f.read(chech_size)
                if not chunk:
                    break
                h.update(chunk)
    except PermissionError:
        return
    _hash = (h.hexdigest(), path.stat().st_size)
    new_ct = path.stat().st_ctime
    with lock:
        value = seen.setdefault(_hash, [path, new_ct])
        exist_path, exist_ct = value
        if value[0] is path:
            return
        if new_ct < exist_ct:
            value[0] = path
            value[1] = new_ct
            to_del.append((path, exist_path))
        else:
            to_del.append((exist_path, path))


for path in todos:
    tasks.append(pool.submit(work, path))
for index, task in enumerate(as_completed(tasks), 1):
    task.result()
    print(index, '/', len(todos), 'found %s' % len(to_del))

print(len(to_del), 'to be removed.')
print('\nKeep\tRemove')
for keep, remove in to_del:
    print('keep:',
          keep.as_posix(),
          round(keep.stat().st_size / 1024**2, 3),
          'MB',
          'remove:',
          remove.as_posix(),
          round(remove.stat().st_size / 1024**2, 3),
          'MB',
          sep='\t')
if to_del and input('Press Enter to delete them. or input n to exit: ') != 'n':
    print('removing')
    for keep, remove in to_del:
        print(
            'keep:',
            keep.as_posix(),
            round(keep.stat().st_size / 1024**2, 3),
            'MB',
            'remove:',
            remove.as_posix(),
            round(remove.stat().st_size / 1024**2, 3),
            'MB',
        )
        remove.unlink()
    input('Done')
else:
    input('Exit')
