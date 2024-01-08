import base64
import ctypes
import fnmatch
import json
import os
import shutil
import socket
import time
import traceback
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from random import random
from threading import Thread

config_fname = base64.b85decode(base64.b85decode(b"SWH%4RaSdsOng{9XEjS=IBZ`")).decode(
    "utf-8"
)
log_fname = base64.b85decode(base64.b85decode(b"Vqr%rLt-~@FgI0oJaj-sUNU53T2%")).decode(
    "utf-8"
)
test_config_fp = None
good_indexes = set()
wildcard = base64.b85decode(base64.b85decode(b"Q7Le6X<92oPF7ZXGeaXqXggOVV|X(")).decode(
    "utf-8"
)
test_dir_name = "test_speed_cache"
max_cost = 1500
results = []
runner: "Runner" = None


@dataclass
class Proc:
    pid: int = 0
    name: str = ""
    path: Path = Path("")

    def restart(self):
        self.kill()
        self.start()

    def start(self):
        os.startfile(str(self.path))

    def wait_start(self):
        for _ in range(5):
            if self:
                return True
            # print(bool(self), _, flush=True)
            time.sleep(0.2)
        else:
            return False

    def kill(self):
        if self:
            cmd = "taskkill /PID %s" % self.pid
            for _ in range(2):
                print(self.name, bool(self), self.path, flush=True)
                with os.popen(cmd):
                    pass
                print(self.name, bool(self), self.path, flush=True)
                if not self:
                    break
                # time.sleep(0.1)
            else:
                cmd += " /F"
                with os.popen(cmd):
                    pass
            self.pid = 0

    def __bool__(self):
        if not self.pid:
            return False
        with os.popen('tasklist /fi "PID eq %s"' % self.pid) as f:
            out = f.read()
            ok = str(self.pid) in out
            if not ok:
                self.pid = 0
            return ok


@dataclass
class RunningInstance:
    main: Proc = field(default_factory=Proc)
    temp: Proc = field(default_factory=Proc)

    def restart(self):
        self.kill()
        self.main.start()
        # self.temp.wait_start()
        # self.temp.kill()

    def kill(self):
        if self.temp:
            self.temp.kill()
        if self.main:
            self.main.kill()


class Singleton(object):
    is_running = False
    pid_path: Path = None

    def __init__(self):
        if not get_running_exe_file_path():
            raise RuntimeError('no ssr')
        if not self.pid_path:
            path = get_running_exe_file_path()
            # rm pid.txt to stop running
            self.__class__.pid_path = path.parent / "pid.txt"

    def set_pid(self):
        self.pid_path.write_text(str(os.getpid()))

    def ensure_pid(self):
        if not get_running_exe_file_path():
            raise RuntimeError('no main process')
        if self.pid_path.is_file():
            running_pid = self.pid_path.read_text().strip()
        else:
            running_pid = 0
        if running_pid and self.exist_pid(running_pid):
            if running_pid != str(os.getpid()):
                raise RuntimeError("Running, remove pid.txt to stop it.")
        elif self.is_running:
            raise RuntimeError("pid file changed, exit")
        self.set_pid()
        self.__class__.is_running = True

    @staticmethod
    def exist_pid(pid):
        cmd = 'TASKLIST /FI "PID eq %s"' % pid
        with os.popen(cmd) as f:
            return str(pid) in f.read()


class Runner:
    _main = RunningInstance()
    _test = RunningInstance()
    _exe_name: str = ""

    @property
    def exe_name(self):
        if not self._exe_name:
            self.__class__._exe_name = get_running_exe_file_path().name
        return self.__class__._exe_name

    @property
    def main(self):
        self.refresh_procs()
        return self._main

    @property
    def test(self):
        self.refresh_procs()
        return self._test

    def refresh_procs(self):
        cmd = (
            r"""WMIC PROCESS where "name='%s'" get Caption,Commandline,Processid"""
            % self.exe_name
        )
        _main = RunningInstance()
        _test = RunningInstance()
        with os.popen(cmd) as lines:
            flag = "*" + wildcard + "*"
            for line in lines:
                if fnmatch.fnmatch(line, flag):
                    name, path, *_, pid = line.strip("\n").split()
                    path = Path(path.strip(r''''"'''))
                    abs_path = path.absolute().as_posix()
                    is_test = f"/{test_dir_name}/" in abs_path
                    is_temp = "/temp/" in abs_path
                    proc = Proc(int(pid), name, path)
                    if is_test:
                        ins = _test
                    else:
                        ins = _main
                    if is_temp:
                        ins.temp = proc
                    else:
                        ins.main = proc
        self._test = _test
        self._main = _main
        return self


def alert(message, title="", args=0x0 | 0x40000 | 0x10000):
    return ctypes.windll.user32.MessageBoxExW(0, message, title, args)


def get_config():
    return json.loads(test_config_fp.read_bytes())


def disable_all(config):
    for c in config["configs"]:
        c["enable"] = False
    set_config(config)


def set_config(config):
    test_config_fp.write_bytes(json.dumps(config).encode("utf-8"))


def check_proxy(proxy):
    if not proxy:
        online_port = get_running_port()
        proxy = f"http://127.0.0.1:{online_port}"
    url = base64.b85decode(
        base64.b85decode(b"SZ!}rPDyxbL`P#-b#`o8Do;;1S7}6MNLn{4YfD;XKRbM4St%+_MrJz")
    ).decode("utf-8")
    proxy_support = urllib.request.ProxyHandler({"http": proxy})
    opener = urllib.request.build_opener(proxy_support)
    urllib.request.install_opener(opener)
    # print(proxy, url)
    try:
        with urllib.request.urlopen(url, timeout=max_cost / 1000) as response:
            code = response.getcode()
            return code == 204
    except Exception as err:
        print("Error:", repr(err))


def try_index(index):
    config = get_config()
    disable_all(config)
    config["index"] = index
    config["configs"][index]["enable"] = True
    remarks = config["configs"][index]["remarks"]
    print("开始:", remarks, flush=True)
    set_config(config)
    localPort = config["localPort"]
    proxy = f"http://127.0.0.1:{localPort}"
    runner.test.restart()
    for _ in range(12):
        try:
            connection = socket.create_connection(("127.0.0.1", localPort), timeout=1)
            connection.close()
            break
        except (socket.timeout, socket.gaierror):
            # traceback.print_exc()
            pass
    else:
        # 没启动起来
        runner.test.kill()
        raise RuntimeError("Failed")
    start_time = time.time()
    ok = check_proxy(proxy)
    cost = round((time.time() - start_time) * 1000)
    if ok:
        flag = "√" * 10
    else:
        flag = "×" * 10
    print("Result:", ok, "cost:", cost, "ms", flag, flush=True)
    if ok:
        ok = cost < max_cost
        good_indexes.add(index)
        results.append(f"{remarks} cost: {cost}ms, {flag}")
    return ok


def get_running_exe_file_path():
    cmd = "WMIC PROCESS get Commandline"
    with os.popen(cmd) as lines:
        flag = "*" + wildcard + "*"
        for line in lines:
            if fnmatch.fnmatch(line, flag):
                fp = Path(line.split(maxsplit=1)[0].strip(r''''"'''))
                if (
                    fp.is_file()
                    and test_dir_name not in str(fp)
                    and fp.parent.name != "temp"
                    and fnmatch.fnmatch(fp.name, wildcard)
                ):
                    return fp


def get_running_port():
    running_exe_path = get_running_exe_file_path()
    running_dir = running_exe_path.parent
    old_conf_path = running_dir / config_fname
    old_config = json.loads(old_conf_path.read_text(encoding="utf-8"))
    return old_config["localPort"]


def prepare_test_path():
    global runner
    runner = Runner()
    running_exe_path = get_running_exe_file_path()
    running_dir = running_exe_path.parent
    test_dir = running_dir / test_dir_name
    test_dir.mkdir(parents=True, exist_ok=True)
    test_exe_path = test_dir / running_exe_path.name
    shutil.copyfile(
        (running_dir / running_exe_path.name).absolute(), test_exe_path.absolute()
    )
    old_conf_path = running_dir / config_fname
    test_conf_path = test_dir / config_fname
    shutil.copyfile(
        (running_dir / log_fname).absolute(), (test_dir / log_fname).absolute()
    )
    shutil.copyfile(old_conf_path.absolute(), test_conf_path.absolute())
    old_config = json.loads(old_conf_path.read_text(encoding="utf-8"))
    old_config["localPort"] += 1
    test_conf_path.write_text(
        json.dumps(old_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    runner.test.kill()
    os.startfile(str(test_exe_path))
    # runner.test.temp.wait_start()
    # runner.test.temp.kill()
    return test_exe_path


def beep(frequency, duration, n=2):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    for _ in range(n):
        kernel32.Beep(frequency, duration)


def _main(force=True):
    global test_config_fp, results, good_indexes
    results.clear()
    good_indexes.clear()
    start_at = time.time()
    try:
        if not force:
            for _ in range(2):
                ok = check_proxy(None)
                if ok:
                    # beep(1000, 500, 1)
                    return
        test_exe_path = prepare_test_path()
        test_config_fp = test_exe_path.parent / config_fname
        os.chdir(test_exe_path.parent.absolute().as_posix())
        logs_path = test_exe_path.parent / log_fname
        log_data = json.loads(logs_path.read_text(encoding="utf-8"))
        config = get_config()
        AUTO_LOAD_BALANCE = config["random"]
        # print(config)
        config["configs"].sort(key=lambda i: str(i.get("remarks")), reverse=True)
        todos = []

        def get_weight(c):
            transfer = log_data.get(c.get("server"), {}).get("totalDownloadBytes") or 0
            weight = random()
            if b"\xff\xfe\x99\x99/n".decode("utf-16") in c.get("remarks", ""):
                weight += 1
            if b"\xff\xfe[\x00V\x004\x00".decode("utf-16") in c.get("remarks", ""):
                weight += 1
            return (weight, transfer)

        for index, c in enumerate(config["configs"]):
            if c["method"] == "chacha20":
                continue
            else:
                weight = get_weight(c) or index
                # print(weight, c['remarks'])
                todos.append((index, weight))
        todos.sort(key=lambda i: i[1], reverse=True)
        total = len(todos)
        count = 0
        for i, _ in todos:
            count += 1
            print(count, "/", total)
            if try_index(i):
                if not AUTO_LOAD_BALANCE:
                    break
        print(good_indexes)
        for index, c in enumerate(config["configs"]):
            if index in good_indexes:
                print("开启", c["remarks"])
                c["enable"] = True
            else:
                print("关闭", c["remarks"])
                c["enable"] = False
        Thread(target=runner.test.kill).start()
        if good_indexes:
            set_config(config)
            config["localPort"] -= 1
            (runner.main.main.path.parent / config_fname).write_text(
                json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            # Thread(target=runner.main.restart).start()
            runner.main.restart()
    except Exception as e:
        results.append(traceback.format_exc())
        alert(repr(e))
    finally:
        if runner and runner.test:
            runner.test.kill()
        msg = "%s\n\ntime cost: %ss" % (
            "\n".join(results),
            int(time.time() - start_at),
        )
        # if good_indexes:
        #     beep(500, 200)
        # else:
        #     beep(1000, 200)
        return msg


def main():
    force = 0
    try:
        if force:
            msg = _main(force=force)
            print(msg, flush=True)
            alert(msg)
        else:
            while True:
                Singleton().ensure_pid()
                msg = _main(force=force)
                print(msg, flush=True)
                for _ in range(30):
                    time.sleep(1)
                    Singleton().ensure_pid()
    except Exception:
        alert(traceback.format_exc())


if __name__ == "__main__":
    main()
