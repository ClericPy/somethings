import base64
import json
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

config_fname = base64.b85decode(
    base64.b85decode(b'SWH%4RaSdsOng{9XEjS=IBZ`')).decode('utf-8')
if (Path.cwd() / config_fname).is_file():
    root = Path.cwd()
else:
    root = Path(__file__)

config_fp = root / config_fname


def get_exe_file_names():
    return [
        i.name for i in root.glob(
            base64.b85decode(base64.b85decode(
                b'Q7Le6X<92oPF7ZXGeaXqXggOVV|X(')).decode('utf-8'))
    ]


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


def get_exe_name():
    names = get_exe_file_names()
    if not names:
        raise RuntimeError('未找到配置文件')
    real_name = None
    for name in names:
        real_name = kill_exe(name)
        if real_name:
            break
    if real_name:
        return real_name
    else:
        raise RuntimeError('程序未启动')


def try_index(index, name):
    config = get_config()
    config['index'] = index
    print('开始:', config['configs'][index]['remarks'])
    config_fp.write_bytes(json.dumps(config).encode('utf-8'))
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
    enable = False
    try:
        start_time = time.time()
        # from torequests import tPool
        # print(tPool().get(TESTURL, proxies={'http': PROXY}).status_code == 204, round(time.time()-start_time, 3), '秒')
        with urllib.request.urlopen(url, timeout=2) as response:
            cost = round((time.time() - start_time) * 1000)
            code = response.getcode()
            ok = code == 204
            if ok:
                flag = '√' * 10
            else:
                flag = '×' * 10
            print('结果:', code, 'cost:', cost, 'ms', flag)
            if ok:
                if cost < 500:
                    enable = True
                    return
                # print('三秒后测试下一个, 立刻关闭程序可以保留当前代理')
                # for _ in range(3):
                #     time.sleep(1)
                #     print(3 - _, flush=True, end=' ')
                # print()
    except Exception as err:
        print('出错:', repr(err))
    finally:
        config['configs'][index]['enable'] = enable
        config_fp.write_bytes(json.dumps(config).encode('utf-8'))
        return enable


def main():
    name = get_exe_name()
    config = get_config()
    AUTO_LOAD_BALANCE = config['random']
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
        if try_index(i, name):
            if not AUTO_LOAD_BALANCE:
                break


if __name__ == "__main__":
    try:
        main()
        print('任务成功, 3 秒后结束')
        time.sleep(3)
    except Exception:
        import traceback
        traceback.print_exc()
        input('任务异常, 回车继续')
