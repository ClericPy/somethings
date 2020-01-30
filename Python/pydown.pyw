# -*- coding: utf-8 -*-
# pip install pyperclip requests[socks] PySimpleGUI

import base64
import hashlib
import inspect
import json
import re
import subprocess
import time
import traceback
import webbrowser
from functools import partial
from os import startfile
from pathlib import Path
from queue import Queue
from threading import Event, Thread, Timer
from urllib.parse import urlparse

import psutil
import pyperclip
import PySimpleGUI as sg
import requests
import urllib3
'''
TODO:
1. retry
2. restart
3. resume breakpoint
4. speed up by concurrent
5. some flexible choose_parser strategy (after domain chosen)
6. add more default parse rules
'''

urllib3.disable_warnings()

WATCH_CLIP = Event()
WATCH_CLIP.set()
REFRESH_TABLE_INTERVAL = 2.5
CLIPBOARD_LISTENER_INTERVAL = 0.2
VERSION = '0.0.2'
# ===========
PROXY = '127.0.0.1:1080'
REQUEST_PROXY = {'https': f'http://{PROXY}', 'http': f'http://{PROXY}'}
REQUEST_HEADERS = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Dnt': '1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 8.0; Pixel 2 Build/OPD3.170816.012) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Mobile Safari/537.36',
    'Sec-Fetch-User': '?1',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'navigate',
    'Referer': '',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Cookie': 'html5_pref=; cit=%3D%3D; 5df592085d7190=1; HEXAVID_LOGIN=; thumbloadstats_vthumbs=; last_views=; xv_nbview=3; html5_networkspeed=80479; bs=; ss=; _ga=GA1.2.151826758.1568994485; RNLBSERVERID=; RNKEY=; views=2; ua=; platform_cookie_reset=mobile; platform=mobile'
}
CHUNK_SIZE = 1024 * 100  # 100KB
# ===========
WINDOW_BG = '#E0E0E0'
GLOBAL_BAR_COLOR = ('#76FF03', '#607D8B')
GLOBAL_BUTTON_COLOR = ('#212121', '#EEEEEE')
# ===========
SAVING_DIR = Path.cwd().absolute() / 'Downloads'
if not SAVING_DIR.is_dir():
    SAVING_DIR.mkdir()
DOWNLOADING_DIR = SAVING_DIR / 'Downloading'
if not DOWNLOADING_DIR.is_dir():
    DOWNLOADING_DIR.mkdir()


def get_screensize(zoom=1):
    import ctypes
    user32 = ctypes.windll.user32
    # (2560, 1440)
    screensize = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    return list(int(i * zoom) for i in screensize)


def open_dir(path: Path = SAVING_DIR.absolute()):
    try:
        subprocess.Popen(['explorer.exe', str(path)], shell=False)
    except FileNotFoundError as e:
        GUI.msg = str(e)


def clear_clipboard(second=5):
    timer = Timer(5, pyperclip.copy, [''])
    timer.setDaemon(True)
    timer.start()


class Sound(object):

    def __init__(self):
        try:
            import winsound
            self.winsound = winsound
            self.beep(1, 37, 0)
        except ImportError:
            self.winsound = None

    def start(self):
        self.beep(1, 1000, 150, 0.2)

    def ok(self):
        self.beep(2, 1000, 150)

    def error(self):
        self.play_sound('SystemHand')

    def play_sound(self, msg):
        if self.winsound:
            self.winsound.PlaySound(msg, self.winsound.SND_ASYNC)

    def beep(self, n, f, d, interval=0.1):
        if self.winsound:
            for _ in range(n):
                self.winsound.Beep(f, d)
                time.sleep(interval)


class GUI(object):
    msg = ''
    sound = Sound()

    def __init__(self):
        self.window = None
        self.downloader = Downloader()
        self.table_values = []
        self.watch_clip = False
        self.global_pause = False
        self._shutdown = False

    @property
    def x(self):
        return self.run()

    def add_parser(self, url, function):
        return self.downloader.add_parser(url, function)

    def del_parser(self, url):
        return self.downloader.del_parser(url)

    def test_parser(self, url):
        return self.downloader.test_parser(url)

    def refresh_proxy(self):
        if not self.window:
            return REQUEST_PROXY

    def __enter__(self):
        return self

    def __exit__(self, *args, **kws):
        self.shutdown()

    def refresh(self):
        self.window.Read(0)

    def refresh_table(self):
        self.refresh_status_bar()
        tmp = self.table_values
        self.table_values = [[
            i.meta.title,
            i.status.title(), i.meta.duration,
            f'{round(i.current_size/1024/1024, 1)}/{round(i.size/1024/1024, 1)} MB',
            i.speed, i.timeleft, i.state
        ] for i in self.downloader.tasks]
        if tmp != self.table_values:
            self.update('table', self.table_values)

    def refresh_table_loop(self):
        while 1:
            self.refresh_table()
            time.sleep(REFRESH_TABLE_INTERVAL)

    def refresh_status_bar(self):
        num = len([i for i in DOWNLOADING_DIR.iterdir() if i.is_file()])
        self.update('status_bar', f"Downloading: {num}. {self.msg}")

    def add_task(self, url=None):
        if not url:
            url = pyperclip.paste()
        if not url.startswith('http'):
            return
        if self.downloader.only_copy:
            meta = self.downloader.get_meta(url)
            if meta:
                pyperclip.copy(meta.url)
            return
        task = self.downloader.current_downloader(url)
        if task:
            self.refresh_table()

    def get_selected_tasks(self):
        tasks = []
        indexes = self.window['table'].SelectedRows
        if self.table_values and not indexes:
            GUI.msg = 'Choose at lease one row of this table.'
            return tasks
        for index in indexes:
            try:
                title = self.table_values[index][0]
                task = self.downloader.tasks[index]
                if title != task.meta.title:
                    continue
                tasks.append(task)
            except IndexError:
                continue
        return tasks

    def check_current_proxy(self, current_proxy=None):
        global PROXY
        if current_proxy is not None:
            PROXY = current_proxy
        if PROXY and self.downloader.check_proxy():
            proxy = PROXY if '://' in PROXY else f'http://{PROXY}'
            REQUEST_PROXY.update({'https': proxy, 'http': proxy})
            self.window['current_proxy'].Update(text_color='green')
        else:
            REQUEST_PROXY.clear()
            self.window['current_proxy'].Update(text_color='red')
            self.window['use_proxy'].Update(value=False)
            PROXY = ''

    def start_daemon_functions(self):
        Thread(target=self.refresh_table_loop, daemon=True).start()
        Thread(target=self.clipboard_listener_loop, daemon=True).start()
        Thread(target=self.downloader.run, daemon=True).start()

    def run(self):
        if not self.window:
            self.init_window()
        self.start_daemon_functions()
        self.refresh_status_bar()
        self.check_current_proxy()
        while 1:
            event, values = self.window.Read()
            # print(event, values)
            if event in {None, 'Exit'}:
                break
            elif event == 'new':
                url = pyperclip.paste()
                if self.downloader.choose_parser(url):
                    self.add_task(url)
                else:
                    ok = sg.PopupYesNo(
                        f'Not support this url: {url}, force download?')
                    if ok == 'Yes':
                        if url.startswith('http'):
                            meta = VideoMeta(url, url)
                            self.downloader.download(url=url, meta=meta)
                        else:
                            sg.PopupOK('invalid url')
                continue
            elif event == 'view_downloads':
                open_dir()
                continue
            elif event in {'help', 'F1:112'}:
                sg.Popup(
                    '''
1. Press `New` button, will load url from Clipboard manually
2. Press `Pause` button, to pause all downloading tasks
3. Select some tasks from the table, Press `Delete` button (or press keyboard `Del`) to delete the files created by them
4. Press `Downloads` button, to open the folder, only for windows explorer.exe
5. Select `Listen Clipboard`, will auto create task from Clipboard change
6. Uncheck the `127.0.0.1:1080`, will disable the proxy
7. `Sub Folder` for saving files, instead of url netloc as dir name
8. Double Click tasks of the table, will open url in the webbrowser if task not ok, will open file if task is ok''',
                    font=('Mono', 18))
                continue
            elif event == 'pause':
                self.switch_pause_download()
                continue
            elif event == 'use_proxy':
                self.check_current_proxy(values['current_proxy'])
            elif event == 'watch_clip':
                if values[event]:
                    WATCH_CLIP.set()
                else:
                    WATCH_CLIP.clear()
                continue
            elif event in {'Delete', 'Delete:46', 'Webview', 'Folder'}:
                tasks = self.get_selected_tasks()
                for task in tasks:
                    if 'Delete' in event:
                        task.cancel()
                        task.del_all_files()
                        self.downloader.tasks.remove(task)
                        del task
                    elif event == 'Webview':
                        webbrowser.open_new_tab(task.meta.origin)
                    elif event == 'Folder':
                        open_dir(task.saving_path)
                self.rm_null_dir(rm_all=0)
            elif event == 'a:65':
                self.window['table'].Update(
                    select_rows=list(range(len(self.window['table'].Values))))
                continue
            elif values['current_proxy'] != PROXY:
                # clear proxy on change
                self.window['use_proxy'].Update(value=False)
                REQUEST_PROXY.clear()
                continue
            elif event in ('default_downloader', 'thunder_downloader',
                           'fdm_downloader'):
                self.update_current_downloader(values)
                continue
            elif event == 'only_copy':
                self.downloader.only_copy = values[event]
                continue
        self.shutdown()

    def update_current_downloader(self, values):
        for name in ('default_downloader', 'thunder_downloader',
                     'fdm_downloader'):
            if values[name]:
                self.downloader.current_downloader = self.downloader.get_downloader(
                    name)

    def shutdown(self):
        if self._shutdown:
            return
        if self.window:
            self.window.Close()
            del self.window
        self.downloader.shutdown()
        self.clean_downloading_dir()
        self.rm_null_dir(rm_all=1)
        self._shutdown = True

    def __del__(self):
        self.shutdown()

    def rm_null_dir(self, rm_all=False):
        if SAVING_DIR.is_dir():
            downloading_name = DOWNLOADING_DIR.name
            for folder in SAVING_DIR.iterdir():
                if folder.name == downloading_name and not rm_all:
                    continue
                if folder.is_dir():
                    self.rmdir(folder)
        if rm_all:
            self.rmdir(SAVING_DIR)

    def rmdir(self, path):
        try:
            path.rmdir()
            return True
        except OSError:
            return False

    def clean_downloading_dir(self):
        if DOWNLOADING_DIR.is_dir():
            for path in DOWNLOADING_DIR.iterdir():
                try:
                    path.unlink()
                finally:
                    pass

    def switch_pause_download(self):
        if self.global_pause:
            # if pause, switch to continue
            self.global_pause = False
            self.update('pause', ' Pause ')
            for task in self.downloader.tasks:
                task.unpause()
        else:
            # if continue, switch to pause
            self.global_pause = True
            self.update('pause', ' Continue ')
            for task in self.downloader.tasks:
                task.pause()

    def clipboard_listener_loop(self):
        url = pyperclip.paste()
        while 1:
            WATCH_CLIP.wait()
            new_url = (pyperclip.paste() or '').strip()
            if new_url and new_url != url:
                self.add_task(new_url)
                url = new_url
            time.sleep(CLIPBOARD_LISTENER_INTERVAL)

    def update(self, key, value):
        self.window[key].Update(value)
        self.refresh()

    def init_window(self):
        half_screen_size = get_screensize(zoom=0.5)
        button_font = ('Mono', 18)
        width = half_screen_size[0]
        self.layouts = [
            [
                sg.Button(
                    ' New ',
                    key='new',
                    font=button_font,
                    tooltip=' Add Task from Clipboard URL ',
                    pad=(10, 10),
                    auto_size_button=1),
                sg.Button(
                    ' Pause ',
                    key='pause',
                    font=button_font,
                    pad=(10, 10),
                    auto_size_button=1),
                sg.Button(
                    ' Delete ',
                    key='Delete',
                    font=button_font,
                    pad=(10, 10),
                    auto_size_button=1),
                sg.Button(
                    ' Downloads ',
                    key='view_downloads',
                    font=button_font,
                    tooltip=f' Open dir {SAVING_DIR} ',
                    pad=(10, 10),
                    auto_size_button=1),
                sg.Exit(
                    ' Exit ',
                    font=button_font,
                    pad=(10, 10),
                    key='Exit',
                    auto_size_button=1),
                sg.Button(' ? ', key='help', tooltip='`F1` for shortcut.'),
                sg.Checkbox(
                    'Listen Clipboard',
                    change_submits=1,
                    default=1,
                    background_color=WINDOW_BG,
                    text_color='black',
                    tooltip=' Auto download url from Clipboard ',
                    key='watch_clip',
                    font=('Mono', 15)),
            ],
            [
                sg.Checkbox(
                    'Proxy: ',
                    change_submits=1,
                    default=1,
                    background_color=WINDOW_BG,
                    text_color='black',
                    key='use_proxy',
                    font=('Mono', 15),
                ),
                sg.Input(
                    PROXY,
                    key='current_proxy',
                    size=(15, 1),
                    change_submits=1,
                    tooltip=' Update proxy for new task ',
                ),
                sg.Text(
                    'Downloader:',
                    background_color=WINDOW_BG,
                    text_color='black',
                    font=('Mono', 12),
                ),
                sg.Radio(
                    'Default',
                    change_submits=1,
                    default=1,
                    background_color=WINDOW_BG,
                    tooltip=' Run the downloader before using it ',
                    text_color='black',
                    key='default_downloader',
                    group_id='choose_downloader',
                    disabled=0,
                    font=('Mono', 15),
                ),
                sg.Radio(
                    'Thunder',
                    change_submits=1,
                    default=bool(self.downloader.thunder_downloader),
                    background_color=WINDOW_BG,
                    tooltip='Run the downloader at first to enable it',
                    text_color='black',
                    key='thunder_downloader',
                    group_id='choose_downloader',
                    disabled=not self.downloader.thunder_downloader,
                    font=('Mono', 15),
                ),
                sg.Radio(
                    'FDM',
                    change_submits=1,
                    default=bool(self.downloader.fdm_downloader),
                    background_color=WINDOW_BG,
                    tooltip='Run the downloader at first to enable it',
                    text_color='black',
                    key='fdm_downloader',
                    group_id='choose_downloader',
                    disabled=not self.downloader.fdm_downloader,
                    font=('Mono', 15),
                ),
                sg.Checkbox(
                    'SkipDownload',
                    change_submits=1,
                    default=self.downloader.only_copy,
                    background_color=WINDOW_BG,
                    tooltip=
                    'Do not download, only copy result url to clipboard.',
                    text_color='black',
                    key='only_copy',
                    font=('Mono', 15),
                ),
            ],
            [
                sg.Text(
                    '',
                    font=('Mono', 12),
                    key='status_bar',
                    text_color='black',
                    background_color=WINDOW_BG,
                    size=(999, 1)),
            ],
            [
                sg.Table(
                    self.table_values,
                    background_color='#ecf0f1',
                    select_mode=sg.TABLE_SELECT_MODE_EXTENDED,
                    text_color='black',
                    font=('Mono', 12),
                    key='table',
                    headings=[
                        'Title', 'Status', 'Duration', 'Size', 'Speed',
                        'Timeleft', 'Progress'
                    ],
                    header_font=('Mono', 18),
                    auto_size_columns=0,
                    justification='center',
                    display_row_numbers=True,
                    right_click_menu=['', ['&Webview', '&Folder', '&Delete']],
                    num_rows=999,
                    vertical_scroll_only=0,
                    tooltip='Double click to open file or pause task'
                    '; Ctrl-A to select all rows; Press `DEL` to delete',
                    col_widths=[
                        int(40 / 100 * width * 0.1),
                        int(10 / 100 * width * 0.1),
                        int(13 / 100 * width * 0.1),
                        int(10 / 100 * width * 0.1),
                        int(10 / 100 * width * 0.1),
                        int(12 / 100 * width * 0.1),
                        int(15 / 100 * width * 0.1),
                    ])
            ],
        ]
        self.window = sg.Window(
            f'Downloader ({SAVING_DIR}) v{VERSION}',
            self.layouts,
            size=half_screen_size,
            return_keyboard_events=True,
            finalize=1,
            element_padding=(5, 0),
            background_color=WINDOW_BG,
            button_color=GLOBAL_BUTTON_COLOR,
            resizable=1)
        self.window['table'].Widget.bind('<Double-Button-1>', self.dbclick_cb)
        self.refresh()

    def dbclick_cb(self, event):
        tasks = self.get_selected_tasks()
        for task in tasks:
            if task.status == 'ok':
                # open file
                try:
                    startfile(task.file_path)
                except OSError as e:
                    GUI.msg = str(e)
            else:
                task.switch_pause()


class Task(object):

    def __init__(self, meta, session, saving_path):
        self.f = None
        self.status = 'todo'
        self.saving_path = saving_path
        if not self.saving_path.is_dir():
            self.saving_path.mkdir()
        self.meta = meta
        self.downloading_file_path: Path = DOWNLOADING_DIR / self.meta.file_name
        self.session = session
        self.speed = '0 KB/S'
        self.timeleft = '-'
        self.state = '-'
        self.size = 0
        self.current_size = 0
        self.working_space = Event()
        self.working_space.set()

    @property
    def file_path(self) -> Path:
        return self.saving_path / self.meta.file_name

    def pause(self):
        if self.status in {'todo', 'downloading'}:
            self.working_space.clear()
            self.status = 'pause'

    def unpause(self):
        if self.status == 'pause':
            self.working_space.set()
            self.status = 'downloading'

    def switch_pause(self):
        if self.status == 'pause':
            self.unpause()
        else:
            self.pause()

    @staticmethod
    def get_percent(current, total):
        if total:
            return round(current * 100 / total)
        else:
            return

    @staticmethod
    def get_proc(percent):
        if not percent:
            return 'Unknown'
        percent = min((percent, 100))
        num = percent // 10
        return f"{percent: >3}% [{'='*num: <10}]"

    def wait_pause(self, timeout=None):
        return self.working_space.wait(timeout=timeout)

    def download(self):
        try:
            self.wait_pause()
            r = self.session.get(self.meta.url, timeout=(5, None), stream=True)
        except requests.RequestException as e:
            GUI.msg = str(e)
            self.state = str(e)
            r.close()
            return
        if not re.match(r'.*\.\w+$', self.meta.file_name):
            ext = (r.headers.get('content-type') or 'text/txt').split(
                ';', 1)[0].split('/')[1] or ''
            if ext:
                self.meta.file_name = f'{self.meta.file_name}.{ext}'
        if self.file_path.is_file():
            self.state = 'Exist'
            self.status = 'ok'
            GUI.sound.ok()
            return
        self.size = int(r.headers.get('Content-Length') or 0)
        start_ts = time.time()
        start_size = 0
        self.status = 'downloading'
        self.wait_pause()
        try:
            self.f = open(self.downloading_file_path, 'wb')
            for index, chunk in enumerate(
                    r.iter_content(chunk_size=CHUNK_SIZE), 1):
                # block for pause button
                self.wait_pause()
                if self.status == 'cancel':
                    break
                if self.f.closed:
                    break
                elif chunk:
                    self.f.write(chunk)
                self.current_size = index * CHUNK_SIZE
                now = time.time()
                diff = self.current_size - start_size
                speed = round(diff / (now + 0.001 - start_ts) / 1024, 1)
                self.speed = f'{speed} KB/S'
                if self.size:
                    if self.current_size > self.size:
                        self.current_size = self.size
                    percent = self.get_percent(self.current_size, self.size)
                    self.state = self.get_proc(percent)
                    self.timeleft = f'{round(self.size/1024/(speed+0.001))} s'
                if index % 20 == 0:
                    # reset each 20 chunk, 2 MB
                    start_ts = now
                    start_size = self.current_size
            else:
                self.status = 'ok'
                GUI.sound.ok()
        except Exception as err:
            self.status = str(err)
            GUI.sound.error()
        finally:
            r.close()
            self.f.close()
        self.timeleft = '0 s'
        if self.status == 'ok':
            GUI.msg = 'Download success.'
            # move
            if not self.file_path.is_file():
                self.downloading_file_path.rename(self.file_path)
        else:
            # remove
            self.del_downloading()

    def start(self):
        Thread(target=self.download, daemon=True).start()

    def cancel(self):
        self.status = 'cancel'
        self.unpause()
        self.del_downloading()

    def del_downloading(self):
        self.ensure_file_closed()
        if self.downloading_file_path.is_file():
            try:
                self.downloading_file_path.unlink()
            except PermissionError:
                pass

    def del_file(self):
        if self.file_path.is_file():
            self.file_path.unlink()

    def del_all_files(self):
        self.del_downloading()
        self.del_file()

    def ensure_file_closed(self):
        if self.f and not self.f.closed:
            self.f.close()

    def __del__(self):
        if self.status != 'ok':
            self.del_downloading()

    def __str__(self):
        return f"<Task ({self.status}) {self.meta.title}>"


class VideoMeta(object):
    __slots__ = ('url', 'title', 'file_name', 'duration', 'origin')

    def __init__(self, url, origin=None, title=None, duration=None):
        self.url = url
        self.origin = origin
        self.file_name = f'{self.get_safe_file_name(title, self.url)}'
        self.title = title or self.file_name
        self.duration = self.format_duration(duration)

    @staticmethod
    def format_duration(duration):
        duration = int(duration or 0)
        if not duration:
            return 'unknown'
        if duration > 60:
            return f'{duration // 60} mins'
        else:
            return f'{duration} secs'

    @staticmethod
    def clean_unsafe_file_name(name):
        if name:
            return re.sub(r'[^ \w]+', '_', name).strip()

    @classmethod
    def get_safe_file_name(cls, title, url):
        safe_title = str(cls.clean_unsafe_file_name(title) or '')
        return safe_title or cls.get_url_name(url) or f'{cls.get_time_title()}'

    @staticmethod
    def get_time_title():
        return f"{time.strftime('%Y%m%d%H%M%S')}"

    @staticmethod
    def get_url_name(url):
        path = urlparse(url).path.strip()
        name = Path(path).name if path else ''
        return name

    def to_dict(self):
        return {key: getattr(self, key) for key in self.__slots__}

    def to_json(self, **kwargs):
        return json.dumps(self.to_dict(), **kwargs)

    def __str__(self):
        return self.to_json(ensure_ascii=False)


def find_one(pattern, string, index=1, **kwargs):
    match = re.search(pattern, string, **kwargs)
    if match:
        try:
            return match.group(index)
        except IndexError:
            return ''
    return ''


class Downloader(object):

    def __init__(self):
        self.thunder_downloader = self.get_thunder_downloader()
        self.fdm_downloader = self.get_fdm_downloader()
        self.current_downloader = self.get_downloader()
        self.only_copy = False
        self.session = self.get_session()
        self.tasks = []
        self.parse_rules = {
            'b0bf4f6b72360600': self.php,
            '8f1ff97084320da8': self.php,
            '88c4944f901bba10': self.php,
            'fbb76743b256432b': self.php,
            '19e70fe4181af8cb': self.php,
            '40149afb65ad664b': self.php,
            '5343d0a7e812e740': self.php,
            'a0e485af8a15e33c': self.php,
            '23a56f9969760906': self.php,
            'e59a9a326dca06bb': self.php,
            '8e0f2bd7ed83076a': self.php,
            '1cd8ac82749d3974': self.php,
            '8fae9b7dc1431376': self.xvp,
        }
        self.q = Queue()

    def get_downloader(self, name=None):
        return {
            'default_downloader': self._default_downloader_add_task,
            'thunder_downloader': self._thunder_downloader_add_task,
            'fdm_downloader': self._fdm_downloader_add_task,
        }.get(name, self._default_downloader_add_task)

    def _default_downloader_add_task(self, url):
        return self.add_queue(url)

    def _thunder_downloader_add_task(self, url):
        meta = self.get_meta(url)
        pyperclip.copy(meta.file_name)
        clear_clipboard()
        self.add_thunder_task(meta.url, meta.file_name)

    def _fdm_downloader_add_task(self, url):
        meta = self.get_meta(url)
        self.add_fdm_task(meta.url, meta.file_name)

    @staticmethod
    def ensure_parser_function(function):
        args = inspect.getfullargspec(function).args
        if not (len(args) == 2 and args[0] == 'self'):
            raise ValueError(
                'Parser function args should like def function(self, url):')

    def add_parser(self, url, function):
        self.ensure_parser_function(function)
        host_md5 = self.get_host_md5(url)
        self.parse_rules[host_md5] = partial(function, self)

    def del_parser(self, url):
        host_md5 = self.get_host_md5(url)
        return self.parse_rules.pop(host_md5, None)

    def test_parser(self, url):
        """return VideoMeta or None"""
        return self.get_meta(url)

    @staticmethod
    def get_host_md5(url, n=16):
        m = hashlib.md5()
        host = urlparse(url).netloc
        m.update(host.encode('u8'))
        result = m.hexdigest()[(32 - n) // 2:(n - 32) // 2]
        return result

    @staticmethod
    def get_session(session=None):
        session = session or requests.Session()
        session.proxies = REQUEST_PROXY
        session.stream = True
        session.verify = False
        session.headers = REQUEST_HEADERS
        return session

    @staticmethod
    def check_proxy():
        try:
            return requests.head(
                'http://www.python.org/',
                timeout=(1.5, 1),
                proxies={
                    'http': f'http://{PROXY}',
                    'https': f'http://{PROXY}',
                }).headers.get('Content-Length') == '0'
        except requests.exceptions.RequestException:
            GUI.msg = 'Check proxy fail.'
            return False

    @staticmethod
    def get_thunder_url(url):
        return ("thunder://".encode("utf-8") + base64.b64encode(
            ('AA' + url + 'ZZ').encode("utf-8"))).decode("utf-8")

    @staticmethod
    def get_thunder_downloader():
        for proc in psutil.process_iter():
            try:
                pname = proc.name()
                if pname == 'Thunder.exe':
                    return proc.cmdline()[0]
            except Exception:
                pass

    @staticmethod
    def get_fdm_downloader():
        for proc in psutil.process_iter():
            try:
                pname = proc.name()
                if pname == 'fdm.exe':
                    return proc.cmdline()[0]
            except Exception:
                pass

    def add_thunder_task(self, url, file_name):
        thunder_url = self.get_thunder_url(url)
        if self.thunder_downloader and thunder_url:
            subprocess.Popen([
                self.thunder_downloader, '-StartType:DesktopIcon', thunder_url,
                file_name
            ]).wait()

    def add_fdm_task(self, url, file_name):
        if self.fdm_downloader and url:
            subprocess.Popen([self.fdm_downloader, url]).wait()

    def choose_parser(self, url):
        host_md5 = self.get_host_md5(url)
        return self.parse_rules.get(host_md5)

    def get_meta(self, url):
        parser = self.choose_parser(url)
        # print(parser, 'for', url)
        if not parser:
            # GUI.msg = 'No parser rule matched.'
            return
        try:
            result = parser(url)
            if not result:
                return
            GUI.msg = f'[Got meta]: {result.title}'
            GUI.sound.start()
            return result
        except (json.JSONDecodeError, IndexError, ValueError, IOError, KeyError,
                ZeroDivisionError) as e:
            GUI.msg = str(e)
            traceback.print_exc()
            return

    def xvp(self, origin):
        for _ in range(1, 3):
            try:
                r = self.session.get(origin, timeout=(1.5, 5))
                scode = r.text
                if 'html5player.setVideoUrlHigh' in scode:
                    break
            except requests.RequestException as e:
                GUI.msg = str(e)
                traceback.print_exc()
                continue
        else:
            return None
        url = find_one(r"html5player\.setVideoUrlHigh\('(http[^']*?)'\);",
                       scode)
        duration = find_one(r'property="og:duration" content="(\d+)"',
                            scode) or ''
        title = find_one(r"html5player\.setVideoTitle\('(.*?)'\);", scode)
        if url:
            return VideoMeta(url, origin, title, duration)

    def php(self, origin):
        for _ in range(1, 3):
            try:
                r = self.session.get(origin, timeout=(1.5, 5))
                scode = r.text
                if 'qualityItems_' in scode:
                    break
            except requests.RequestException as e:
                GUI.msg = str(e)
                traceback.print_exc()
                continue
        else:
            return None
        match = find_one(
            r'var flashvars_[^=]* = ([\s\S]*?);\s*var player_mp4_seek', scode)
        if not match:
            return None
        meta = json.loads(match)
        if meta:
            title = meta.get('video_title') or ''
            duration = meta.get('video_duration') or ''
            items = [
                i for i in meta.get('mediaDefinitions') or []
                if i.get('format') == 'mp4'
            ]
            if items:
                url = items[0]['videoUrl']
                return VideoMeta(url, origin, title, duration)

    def add_queue(self, url, saving_path=SAVING_DIR):
        urls = {i.meta.origin for i in self.tasks}
        if url in urls:
            # print(url, 'exist,', urls)
            return
        todo = (url, saving_path)
        # print('add', url)
        self.q.put(todo)
        return True

    def run(self):
        while 1:
            url, saving_path = self.q.get()
            self.download(url, saving_path)

    def download(self, url, saving_path=SAVING_DIR, meta=None):
        meta = self.get_meta(url) if meta is None else meta
        if not meta:
            return
        # add download task
        task = Task(meta, self.session, saving_path)
        task.start()
        self.tasks.append(task)
        GUI.msg = 'Add new task success.'
        return task

    def shutdown(self):
        for task in self.tasks:
            if task.status != 'ok':
                task.cancel()

    def __del__(self):
        self.shutdown()


def main():
    gui = GUI()
    gui.x


def test_new_parser():

    def new_parser(self, url):
        # r = self.session.get(url)
        return VideoMeta(url, url)

    gui = GUI()
    gui.add_parser('http://ip-api.com/json/', new_parser)
    print(gui.test_parser('http://ip-api.com/json/'))
    gui.x


if __name__ == "__main__":
    main()
    # test_new_parser()
