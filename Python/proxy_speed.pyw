# -*- coding: utf-8 -*-
# pip install torequests pysocks PySimpleGUI

import base64
import ctypes
import json
import socket
import time
import timeit
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Thread

import psutil
import PySimpleGUI as sg
from torequests import tPool
from torequests.utils import UA, ttime

TESTURL = 'https://s.ytimg.com/yts/img/favicon-vfl8qSV2F.ico'
PROXY = 'http://127.0.0.1:1080'
INTERVAL = 2
TRIALS = 3
TIMEOUT = 1
STATUS_COLOR = ''
VERSION = '0.0.3'
PAUSE = False


def get_screensize():
    user32 = ctypes.windll.user32
    # (2560, 1440)
    screensize = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    return list(int(i * 0.5) for i in screensize)


def update_color(window, avg_cost):
    if avg_cost < 150:
        color = '#C6FF00'
    elif avg_cost < 350:
        color = '#00C853'
    elif avg_cost < 550:
        color = '#FFCA28'
    elif avg_cost < 1000:
        color = '#FF5722'
    else:
        color = '#9E9E9E'
    window['status_bar'].Update(background_color=color)


def async_print(window):
    while 1:
        if PAUSE:
            time.sleep(2)
            continue
        err = ''
        req = tPool()
        tasks = [
            req.get(
                TESTURL,
                timeout=TIMEOUT,
                headers={'User-Agent': UA.Chrome},
                proxies={'https': PROXY}) for i in range(TRIALS)
        ]
        if all((i.x for i in tasks)):
            ok = '[ OK ]'
            sig = '√'
        else:
            ok = '[Fail]'
            sig = '×'
        if ok == '[Fail]':
            for r in tasks:
                if not r.x:
                    err = r.error.__class__.__name__
                    break
        cost = [int((r.task_cost_time or 9) * 1000) for r in tasks]
        avg_cost = int(sum(cost) / len(tasks))
        print(f'{sig}[{ttime()}] {ok}: {avg_cost}ms {cost} {err}', end=' ')
        update_color(window, avg_cost)
        cd(INTERVAL)


def cd(secs):
    secs = INTERVAL
    for _ in range(secs, 0, -1):
        print(_, end=' ')
        time.sleep(1)
        if secs != INTERVAL:
            return cd(INTERVAL - secs)
    print()


def main():
    global PROXY, TESTURL, INTERVAL, TRIALS, TIMEOUT, PAUSE
    layouts = [[
        sg.Button(
            'Check Nodes',
            key='test_nodes',
            button_color=('black', 'white'),
            font=('mono', 16)),
        sg.Button(
            'Clear Output',
            key='clear_op',
            button_color=('black', 'white'),
            font=('mono', 16)),
        sg.Button(
            'Pause',
            key='pause',
            button_color=('white', 'green'),
            font=('mono', 16)),
    ],
               [
                   sg.Text('Proxy   :', font=('mono', 16)),
                   sg.Input(
                       PROXY,
                       key='current_proxy',
                       change_submits=True,
                       font=('mono', 16)),
               ],
               [
                   sg.Text('Target  :', font=('mono', 16)),
                   sg.Input(
                       TESTURL,
                       key='current_url',
                       change_submits=True,
                       font=('mono', 16))
               ],
               [
                   sg.Text('Interval:', font=('mono', 16)),
                   sg.Input(
                       INTERVAL,
                       key='current_interval',
                       change_submits=True,
                       font=('mono', 16)),
               ],
               [
                   sg.Text('Trials  :', font=('mono', 16)),
                   sg.Input(
                       TRIALS,
                       key='concurrent',
                       change_submits=True,
                       font=('mono', 16)),
               ],
               [
                   sg.Text('Timeout :', font=('mono', 16)),
                   sg.Input(
                       TIMEOUT,
                       key='timeout',
                       change_submits=True,
                       font=('mono', 16)),
               ], [sg.StatusBar('', size=(999, 1), key='status_bar')],
               [sg.Output(size=(999, 999), key='output', font=("", 16))]]
    window = sg.Window(
        title=f'Speed Tester v{VERSION}',
        layout=layouts,
        size=get_screensize(),
    )
    window.Read(timeout=0)
    print('=' * 40)
    Thread(target=async_print, args=(window,), daemon=True).start()
    while 1:
        event, values = window.Read()
        # print(event, values)
        if event in (None, 'Cancel', 'Exit'):
            break
        elif event == 'current_proxy':
            PROXY = values[event]
        elif event == 'current_url':
            TESTURL = values[event]
        elif event == 'current_interval':
            INTERVAL = abs(int(values[event] or 0)) or 1
        elif event == 'concurrent':
            TRIALS = abs(int(values[event] or 0)) or 1
        elif event == 'timeout':
            TIMEOUT = abs(int(values[event] or 0)) or 1
        elif event == 'clear_op':
            window['output'].Update('')
        elif event == 'test_nodes':
            Thread(target=test_nodes).start()
        elif event == 'pause':
            PAUSE = not PAUSE
            if PAUSE:
                button_color = ('white', 'red')
                text = 'Continue'
            else:
                button_color = ('white', 'green')
                text = 'Pause'
            window['pause'].Update(text, button_color)
    quit()


def get_config():
    process_name = base64.b85decode(b'b7)~?Z+CNVV{3DA').decode()
    for i in psutil.process_iter():
        try:
            if i.name().lower().startswith(process_name):
                path = i.cmdline()[0]
                if 'temp' not in path:
                    path = Path(path).parent / base64.b32decode(
                        b'M52WSLLDN5XGM2LHFZVHG33O').decode()
                    return json.loads(path.read_text('u8'))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess,
                IndexError):
            continue


def check(config):
    config['cost'] = 0
    costs = []
    for _ in range(TRIALS):
        cost = 9999
        try:
            start = timeit.default_timer()
            socket.create_connection((config['server'], config['server_port']),
                                     timeout=2)
            cost = int((timeit.default_timer() - start) * 1000)
        except socket.timeout:
            pass
        except socket.gaierror:
            pass
        finally:
            costs.append(cost)
    config['cost'] = sum(costs) // len(costs)
    return config


def test_nodes():
    configs = get_config()
    pool = ThreadPoolExecutor(100)
    results = [
        i for i in pool.map(check, [c for c in configs['configs']])
        if 0 < i['cost'] < TIMEOUT * 1000
    ]
    results.sort(key=lambda i: i['cost'])
    result = '\n'.join([f'{i["cost"]: >4}\t{i["remarks"]}' for i in results])
    sg.PopupOK(result, title='', font=('mono', 14))


if __name__ == "__main__":
    main()
