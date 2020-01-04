import base64
import hashlib
import json
import re
import subprocess
import time
import traceback
import webbrowser
from pathlib import Path
from queue import Queue
from threading import Event, Thread
from urllib.parse import urlparse

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
5. some flexible choose_parser strategy
6. add more default parse rules
'''


# pip install pyperclip requests[socks] PySimpleGUI

urllib3.disable_warnings()

WATCH_CLIP = Event()
WATCH_CLIP.set()
REFRESH_TABLE_INTERVAL = 2
CLIPBOARD_LISTENER_INTERVAL = 0.2
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
SAVING_DIR = Path(__file__).parent.absolute() / 'mp4'
if not SAVING_DIR.is_dir():
    SAVING_DIR.mkdir()
DOWNLOADING_DIR = SAVING_DIR / 'Downloading'
if not DOWNLOADING_DIR.is_dir():
    DOWNLOADING_DIR.mkdir()


def get_screensize(zoom=0.5):
    import ctypes
    user32 = ctypes.windll.user32
    # (2560, 1440)
    screensize = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    return list(int(i * zoom) for i in screensize)


def open_dir():
    subprocess.Popen(['explorer.exe', str(SAVING_DIR.absolute())], shell=False)


class GUI(object):
    msg = ''

    def __init__(self):
        self.downloader = Downloader()
        self.size = get_screensize()
        self.table_values = []
        self.init_window()
        self.refresh()
        self.watch_clip = False
        self.global_pause = False
        self._shutdown = False
        Thread(target=self.refresh_table_loop, daemon=True).start()
        Thread(target=self.clipboard_listener_loop, daemon=True).start()
        Thread(target=self.downloader.run, daemon=True).start()

    def __enter__(self):
        return self

    def __exit__(self, *args, **kws):
        self.shutdown()

    def refresh(self):
        self.window.Read(0)

    def refresh_table(self):
        tmp = self.table_values
        self.table_values = [[
            i.meta.title, i.state, i.meta.duration,
            f'{round(i.current_size/1024/1024, 1)}/{round(i.size/1024/1024, 1)} MB',
            i.speed, i.timeleft
        ] for i in self.downloader.tasks]
        if tmp != self.table_values:
            self.update('table', self.table_values)
            self.refresh_status_bar()

    def refresh_table_loop(self):
        while 1:
            self.refresh_table()
            time.sleep(REFRESH_TABLE_INTERVAL)

    def refresh_status_bar(self):
        num = len([
            i for i in DOWNLOADING_DIR.iterdir()
            if i.is_file() and i.suffix == '.mp4'
        ])
        self.update('status_bar', f"Downloading: {num}. {self.msg}")

    def add_task(self, url=None):
        if not url:
            url = pyperclip.paste()
        task = self.downloader.add_queue(url, self.get_saving_path(url))
        if task:
            self.refresh_table()

    def get_selected_tasks(self):
        tasks = []
        indexes = self.window['table'].SelectedRows
        if self.table_values and not indexes:
            sg.Popup('Please choose at lease one row of this table.')
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

    def run(self):
        self.refresh_status_bar()
        if not Downloader.check_proxy():
            print('cao cao ')
            self.window['use_proxy'].Update(value=False, disabled=True)
            self.downloader.session.proxies = None
            self.window.Read(0)
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
                    sg.Popup(f'Not support this url: {url}')
                continue
            elif event == 'view_dir':
                open_dir()
                continue
            elif event == 'help':
                sg.Popup('''
1. Press `New` button, will load url from Clipboard manually
2. Press `Pause` button, to pause all downloading tasks
3. Select some tasks from the table, Press `Delete` button (or press keyboard `Del`) to delete the files created by them
4. Press `Folder` button, to open the folder, only for windows explorer.exe
5. Select `Listen Clipboard`, will auto create task from Clipboard change
6. Uncheck the `127.0.0.1:1080`, will disable the proxy
7. `Sub Folder` for saving mp4 files, instead of url netloc as dir name
8. Double Click tasks of the table, will open url in the webbrowser

''')
                continue
            elif event == 'pause':
                self.switch_pause_download()
                continue
            elif event == 'use_proxy':
                if values[event]:
                    self.downloader.session.proxies = REQUEST_PROXY
                else:
                    self.downloader.session.proxies = None
            elif event == 'watch_clip':
                if values[event]:
                    WATCH_CLIP.set()
                else:
                    WATCH_CLIP.clear()
                continue
            elif event in {'Delete', 'Delete:46', 'View'}:
                tasks = self.get_selected_tasks()
                for task in tasks:
                    if 'Delete' in event:
                        task.cancel()
                        task.del_all_files()
                        self.downloader.tasks.remove(task)
                        del task
                    elif event == 'View':
                        webbrowser.open_new_tab(task.meta.origin)
        self.shutdown()

    def shutdown(self):
        if self._shutdown:
            return
        self.window.Close()
        self.downloader.shutdown()
        self.clean_downloading_dir()
        self._shutdown = True

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
                task.working_space.set()
        else:
            # if continue, switch to pause
            self.global_pause = True
            self.update('pause', ' Continue ')
            for task in self.downloader.tasks:
                task.working_space.clear()

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

    def get_saving_path(self, url):
        sub_dir = self.window['sub_dir'].Get()
        if not sub_dir:
            sub_dir = VideoMeta.clean_unsafe_file_name(
                urlparse(url).netloc) or ''
        path = SAVING_DIR / sub_dir
        # print(path)
        return path

    def init_window(self):
        button_font = ('', 18)
        width = self.size[0]
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
                    ' Folder ',
                    key='view_dir',
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
                sg.Button(' ? ', key='help'),
                sg.Checkbox(
                    'Listen Clipboard',
                    change_submits=1,
                    default=1,
                    background_color=WINDOW_BG,
                    text_color='black',
                    tooltip=' Auto download url from Clipboard ',
                    key='watch_clip',
                    font=('', 15)),
            ],
            [
                sg.Checkbox(
                    PROXY,
                    change_submits=1,
                    default=1,
                    background_color=WINDOW_BG,
                    text_color='black',
                    key='use_proxy',
                    font=('', 15),
                ),
                sg.Text(
                    'Sub Folder:',
                    background_color=WINDOW_BG,
                    text_color='black',
                    font=('', 12),
                ),
                sg.Input(
                    '',
                    key='sub_dir',
                    size=(10, 1),
                    font=('', 15),
                    tooltip=' Sub folder to save files, url netloc to default.',
                ),
                sg.Text(
                    '',
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
                    key='table',
                    headings=[
                        'Title', 'State', 'Duration', 'Size', 'Speed',
                        'Timeleft'
                    ],
                    header_font=('', 18),
                    auto_size_columns=0,
                    justification='center',
                    display_row_numbers=True,
                    right_click_menu=['', ['&Delete', '&View']],
                    num_rows=999,
                    vertical_scroll_only=0,
                    tooltip='Select rows, Press `DEL` to delete;'
                    ' Press `v` to view in browser.',
                    col_widths=[
                        int(40 / 100 * width * 0.1),
                        int(15 / 100 * width * 0.1),
                        int(13 / 100 * width * 0.1),
                        int(10 / 100 * width * 0.1),
                        int(10 / 100 * width * 0.1),
                        int(12 / 100 * width * 0.1),
                    ])
            ],
        ]
        self.window = sg.Window(
            f'Downloader ({SAVING_DIR})',
            self.layouts,
            size=self.size,
            return_keyboard_events=True,
            finalize=1,
            element_padding=(5, 0),
            background_color=WINDOW_BG,
            button_color=GLOBAL_BUTTON_COLOR,
            resizable=1)
        self.window['table'].Widget.bind('<Double-Button-1>', self.dbclick_cb)

    def dbclick_cb(self, event):
        tasks = self.get_selected_tasks()
        for task in tasks:
            webbrowser.open_new_tab(task.meta.origin)


class Task(object):

    def __init__(self, meta, session, saving_path):
        self.meta = meta
        if not saving_path.is_dir():
            saving_path.mkdir()
        self.file_path: Path = saving_path / meta.file_name
        self.downloading_file_path: Path = DOWNLOADING_DIR / meta.file_name
        self.session = session
        self.speed = '0 KB/S'
        self.timeleft = '-'
        self.state = '-'
        self.status = 'todo'
        self.size = 0
        self.current_size = 0
        self.f = None
        self.working_space = Event()
        self.working_space.set()

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
        proc = f"{percent: >3}% {'#'*num}"
        return f"{proc:=<15}"

    def download(self):
        if self.file_path.is_file():
            self.state = 'Exist'
            return
        try:
            r = self.session.get(self.meta.url, timeout=(5, None), stream=True)
        except requests.RequestException as e:
            GUI.msg = e
            self.state = str(e)
            return
        content_length = r.headers.get('Content-Length')
        if content_length:
            self.size = int(content_length)
        else:
            self.timeleft = self.state = '-'
        start_ts = time.time()
        start_size = 0
        self.status = 'downloading'
        try:
            self.f = open(self.downloading_file_path, 'wb')
            for index, chunk in enumerate(
                    r.iter_content(chunk_size=CHUNK_SIZE), 1):
                # block for pause button
                self.working_space.wait()
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
                    percent = self.get_percent(self.current_size, self.size)
                    self.state = self.get_proc(percent)
                    self.timeleft = f'{round(self.size/1024/(speed+0.001))} s'
                if index % 20 == 0:
                    # reset each 20 chunk, 2 MB
                    start_ts = now
                    start_size = self.current_size
            else:
                self.status = 'ok'
        finally:
            self.f.close()
        self.timeleft = '0 s'
        if self.status == 'ok':
            GUI.msg = 'ok'
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
        self.working_space.set()
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

    def __init__(self, url, title, origin, duration=None):
        self.url = url
        self.title = title
        self.origin = origin
        self.file_name = f'{self.get_safe_file_name(self.title, self.url)}'
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
        safe_title = cls.clean_unsafe_file_name(title)
        if safe_title:
            safe_title = f'{safe_title}.mp4'
        return f'{safe_title}' or cls.get_url_name(
            url) or f'{cls.get_time_title()}.mp4'

    @staticmethod
    def get_time_title():
        return f"{time.strftime('%Y%m%d%H%M%S')}"

    @staticmethod
    def get_url_name(url):
        return find_one(r'([^/]+?\.mp4)', url)

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

    @staticmethod
    def get_host_md5(url, n=16):
        m = hashlib.md5()
        host = urlparse(url).netloc
        m.update(host.encode('u8'))
        result = m.hexdigest()[(32 - n) // 2:(n - 32) // 2]
        return result

    @staticmethod
    def decode(string):
        return base64.b85decode(string.encode('u8')).decode('u8')

    def get_session(self, session=None):
        session = session or requests.Session()
        session.proxies = REQUEST_PROXY
        session.stream = True
        session.verify = False
        session.headers = REQUEST_HEADERS
        return session

    @staticmethod
    def check_proxy():
        try:
            r = requests.get(f'http://{PROXY}', timeout=(1, 1))
            return r.text.strip() == 'Invalid header received from client.'
        except requests.exceptions.ConnectTimeout:
            GUI.msg = 'connect proxy fail.'
            return False

    def choose_parser(self, url):
        host_md5 = self.get_host_md5(url)
        return self.parse_rules.get(host_md5)

    def get_meta(self, url):
        parser = self.choose_parser(url)
        # print(parser, 'for', url)
        if not parser:
            return
        try:
            return parser(url)
        except (json.JSONDecodeError, IndexError, ValueError, IOError, KeyError,
                ZeroDivisionError) as e:
            GUI.msg = e
            traceback.print_exc()
            return

    def xvp(self, origin):
        for _ in range(1, 3):
            try:
                r = self.session.get(origin, timeout=(2, 5))
                scode = r.text
                if 'html5player.setVideoUrlHigh' in scode:
                    break
            except requests.RequestException as e:
                GUI.msg = e
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
            return VideoMeta(url, title, origin, duration)

    def php(self, origin):
        for _ in range(1, 3):
            try:
                r = self.session.get(origin, timeout=(2, 5))
                scode = r.text
                if 'qualityItems_' in scode:
                    break
            except requests.RequestException as e:
                GUI.msg = e
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
                return VideoMeta(url, title, origin, duration)

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

    def download(self, url, saving_path=SAVING_DIR):
        meta = self.get_meta(url)
        if not meta:
            return
        # add download task
        task = Task(meta, self.session, saving_path)
        task.start()
        self.tasks.append(task)
        return task

    def shutdown(self):
        for task in self.tasks:
            if task.status != 'ok':
                task.cancel()

    def __del__(self):
        self.shutdown()


if __name__ == "__main__":
    gui = GUI()
    gui.run()
