# -*- coding: utf-8 -*-
# pip install torequests pysocks PySimpleGUI

import ctypes
import time
from threading import Thread

import PySimpleGUI as sg
from torequests import tPool
from torequests.utils import UA, ttime

TESTURL = 'https://s.ytimg.com/yts/img/favicon-vfl8qSV2F.ico'
PROXY = 'socks5://127.0.0.1:1080'
INTERVAL = 2
TRIALS = 3
TIMEOUT = 2


def get_screensize():
    user32 = ctypes.windll.user32
    # (2560, 1440)
    screensize = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    return list(int(i * 0.5) for i in screensize)


def async_print():
    while 1:
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

        for r in tasks:
            if not r.x:
                err = r.text
                break
        else:
            err = ''
        cost = [int(r.task_cost_time * 1000) for r in tasks]
        avg_cost = int(sum(cost) / len(tasks))
        print(f'{sig}[{ttime()}] {ok}(ms): {cost} => {avg_cost} {err}', end=' ')
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
    global PROXY, TESTURL, INTERVAL, TRIALS, TIMEOUT
    layouts = [[
        sg.Text('Proxy   :', font=('mono', 16)),
        sg.Input(
            PROXY, key='current_proxy', change_submits=True, font=('mono', 16)),
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
               ], [sg.Output(size=(999, 999), key='output', font=("", 16))]]
    window = sg.Window(
        title='Test Speed',
        layout=layouts,
        size=get_screensize(),
    )
    window.Read(timeout=0)
    print('=' * 40)
    Thread(target=async_print, daemon=True).start()
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


if __name__ == "__main__":
    main()