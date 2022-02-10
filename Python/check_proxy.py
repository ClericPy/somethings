import base64
import json
import os
import socket
import subprocess
import time
import urllib.request
import fnmatch
from pathlib import Path

config_fname = base64.b85decode(
    base64.b85decode(b'SWH%4RaSdsOng{9XEjS=IBZ`')).decode('utf-8')
config_fp = None
good_indexes = set()
wildcard = base64.b85decode(
    base64.b85decode(b'Q7Le6X<92oPF7ZXGeaXqXggOVV|X(')).decode('utf-8')


def kill_exe(name):
    try:
        output = subprocess.check_output(f'taskkill /IM {name} /F',
                                         stderr=subprocess.STDOUT)
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
    if AUTO_LOAD_BALANCE:
        max_cost = 1000
    else:
        max_cost = 500
    config['index'] = index
    config['configs'][index]['enable'] = True
    print('开始:', config['configs'][index]['remarks'])
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
        with urllib.request.urlopen(url, timeout=2) as response:
            cost = round((time.time() - start_time) * 1000)
            code = response.getcode()
            ok = code == 204 and cost < max_cost
            if ok:
                flag = '√' * 10
            else:
                flag = '×' * 10
            print('结果:', code, 'cost:', cost, 'ms', flag)
            if ok:
                good_indexes.add(index)
                return True
    except Exception as err:
        print('出错:', repr(err))


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
    name = file_path.name
    config = get_config()
    AUTO_LOAD_BALANCE = config['random']
    if AUTO_LOAD_BALANCE:
        print('检测到负载均衡模式, 保留 1000 ms 以内的所有节点')
    else:
        print('非负载均衡模式, 查找 500ms 以内的节点并切换')
    # print(config)
    best = []
    good = []
    other = []
    for index, c in enumerate(config['configs']):
        if c['method'] == 'chacha20':
            continue
        if '香港' in c['remarks']:
            best.append(index)
        elif '日本' in c['remarks'] or '台湾' in c['remarks']:
            good.append(index)
        else:
            other.append(index)
    for i in best + good + other:
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
        print('任务成功, 3 秒后结束')
        time.sleep(3)
    except Exception:
        import traceback
        traceback.print_exc()
        input('任务异常, 回车继续')
