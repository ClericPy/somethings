import base64
import ctypes
import fnmatch
import json
import os
import socket
import subprocess
import time
import traceback
import urllib.request
from pathlib import Path
from random import random

config_fname = base64.b85decode(
    base64.b85decode(b'SWH%4RaSdsOng{9XEjS=IBZ`')).decode('utf-8')
log_fname = base64.b85decode(
    base64.b85decode(b'Vqr%rLt-~@FgI0oJaj-sUNU53T2%')).decode('utf-8')
config_fp = None
good_indexes = set()
wildcard = base64.b85decode(
    base64.b85decode(b'Q7Le6X<92oPF7ZXGeaXqXggOVV|X(')).decode('utf-8')
results = []


def alert(message, title='', args=0x0 | 0x40000 | 0x10000):
    return ctypes.windll.user32.MessageBoxExW(0, message, title, args)


def kill_exe(name):
    try:
        output = subprocess.check_output(f'taskkill /IM {name} /F',
                                         stderr=subprocess.STDOUT,
                                         shell=True)
        if b' PID ' in output:
            return name
    except subprocess.CalledProcessError:
        return


def get_config():
    return json.loads(config_fp.read_bytes())


def disable_all(config):
    for c in config['configs']:
        c['enable'] = False
    set_config(config)


def set_config(config):
    config_fp.write_bytes(json.dumps(config).encode('utf-8'))


def try_index(index, name, AUTO_LOAD_BALANCE):
    config = get_config()
    disable_all(config)
    # if AUTO_LOAD_BALANCE:
    #     max_cost = 1000
    # else:
    #     max_cost = 500
    max_cost = 2000
    config['index'] = index
    config['configs'][index]['enable'] = True
    remarks = config['configs'][index]['remarks']
    print('开始:', remarks)
    set_config(config)
    localPort = config['localPort']
    PROXY = f'http://127.0.0.1:{localPort}'
    kill_exe(name)
    os.startfile(name)
    for _ in range(5):
        try:
            connection = socket.create_connection(('127.0.0.1', localPort),
                                                  timeout=1)
            connection.close()
            break
        except (socket.timeout, socket.gaierror):
            pass
    else:
        # 没启动起来
        kill_exe(name)
        raise RuntimeError('Failed')
    url = base64.b85decode(
        base64.b85decode(
            b'SZ!}rPDyxbL`P#-b#`o8Do;;1S7}6MNLn{4YfD;XKRbM4St%+_MrJz')).decode(
                'utf-8')
    proxy_support = urllib.request.ProxyHandler({"http": PROXY})
    opener = urllib.request.build_opener(proxy_support)
    urllib.request.install_opener(opener)
    try:
        start_time = time.time()
        # from torequests import tPool
        # print(tPool().get(TESTURL, proxies={'http': PROXY}).status_code == 204, round(time.time()-start_time, 3), '秒')
        with urllib.request.urlopen(url, timeout=max_cost / 1000) as response:
            cost = round((time.time() - start_time) * 1000)
            code = response.getcode()
            ok = code == 204 and cost < max_cost
            if ok:
                flag = '√' * 10
            else:
                flag = '×' * 10
            print('Result:', code, 'cost:', cost, 'ms', flag)
            if ok:
                good_indexes.add(index)
                results.append(f'{remarks} cost: {cost}ms, {flag}')
                return True
    except Exception as err:
        print('Error:', repr(err))


def get_file_path():
    cmd = 'WMIC PROCESS get Caption,Commandline,Processid'
    with os.popen(cmd) as lines:
        flag = '*' + wildcard + '*'
        for line in lines:
            if fnmatch.fnmatch(line, flag):
                fp = Path(line.split()[1].strip(r''''"'''))
                if fp.is_file(
                ) and fp.parent.name != 'temp' and fnmatch.fnmatch(
                        fp.name, wildcard):
                    return fp


def main():
    global config_fp
    file_path = get_file_path()
    config_fp = file_path.parent / config_fname
    os.chdir(file_path.parent.absolute().as_posix())
    logs_path = file_path.parent / log_fname
    log_data = json.loads(logs_path.read_text())
    name = file_path.name
    config = get_config()
    AUTO_LOAD_BALANCE = config['random']
    # print(config)
    config['configs'].sort(key=lambda i: str(i.get('remarks')), reverse=True)
    todos = []

    def get_weight(c):
        transfer = log_data.get(c.get('server'),
                                {}).get('totalDownloadBytes') or 0
        weight = random()
        if b'\xff\xfe\x99\x99/n'.decode('utf-16') in c.get('remarks', ''):
            weight += 1
        if b'\xff\xfe[\x00V\x004\x00'.decode('utf-16') in c.get('remarks', ''):
            weight += 1
        return (weight, transfer)

    for index, c in enumerate(config['configs']):
        if c['method'] == 'chacha20':
            continue
        else:
            weight = get_weight(c) or index
            # print(weight, c['remarks'])
            todos.append((index, weight))
    todos.sort(key=lambda i: i[1], reverse=True)
    # quit()
    total = len(todos)
    count = 0
    for i, _ in todos:
        count += 1
        print(count, '/', total)
        if try_index(i, name, AUTO_LOAD_BALANCE):
            if not AUTO_LOAD_BALANCE:
                break
    print(good_indexes)
    for index, c in enumerate(config['configs']):
        if index in good_indexes:
            print('开启', c['remarks'])
            c['enable'] = True
        else:
            print('关闭', c['remarks'])
            c['enable'] = False
    kill_exe(name)
    os.startfile(name)
    set_config(config)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        results.append(traceback.format_exc())
    alert('\n'.join(results))
