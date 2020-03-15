from pathlib import Path
from tkinter import Tk
from tkinter.messagebox import showerror, showinfo

from pyperclip import paste

top = Tk()
top.withdraw()
top.update()


def run(dir_path: Path):
    counts = 0
    i: Path
    for i in dir_path.glob('**/*.py'):
        if not i.is_file():
            continue
        with open(i, encoding='u8') as f:
            for line in f:
                if line.strip():
                    counts += 1
    showinfo('Total lines of .py file', str(counts))


def main():
    dir_path = paste()
    try:
        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            raise FileNotFoundError(f'{dir_path} is not valid dir path.')
        run(dir_path)
    except Exception as e:
        showerror('Error', repr(e))
    finally:
        top.destroy()


if __name__ == "__main__":
    main()
