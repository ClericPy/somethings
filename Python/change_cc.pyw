import ctypes
import random
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

try:
    from morebuiltins import __version__

    if __version__ < "1.3.0":
        raise ImportError
    from morebuiltins.funcs import threads
    from morebuiltins.request import req
    from morebuiltins.utils import ttime, xor_encode_decode
except ImportError:
    import pip

    pip.main(["install", "morebuiltins>=1.3.0"])
    from morebuiltins.funcs import threads
    from morebuiltins.request import req
    from morebuiltins.utils import ttime, xor_encode_decode


def beep(frequency=800, duration=300, n=3):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    for _ in range(n):
        kernel32.Beep(frequency, duration)


@threads(10)
def test_once(url, return_json=True, proxy=None):
    r = None
    if running:
        try:
            r = req.get(
                url,
                params={"url": test_url, "timeout": timeout},
                headers={"user-agent": "chrome"},
                proxy=proxy,
                timeout=timeout,
            )
        except Exception:
            pass
    if return_json:
        if r:
            return r.json()
        else:
            return {}
    else:
        return r.ok if r else False


@threads(10)
def test_node_delay(proxy_name):
    result = []
    url = api_url + f"/proxies/{quote(proxy_name)}/delay"
    tasks = [test_once(url) for _ in range(tries)]
    for task in tasks:
        delay = task.result().get("delay", timeout * 2)
        result.append(delay)
    return proxy_name, round(sum(result) / len(result))


def check_current_proxy(proxy):
    ok = False
    tasks = [test_once(test_url, return_json=False, proxy=proxy) for _ in range(2)]
    for task in as_completed(tasks):
        ok = task.result()
        if ok:
            print("+", flush=True, end="")
            break
        else:
            print("-", flush=True, end="")
    return ok


timeout = 2000
tries = 3
# test_url = "http://www.gstatic.com/generate_204"
test_url = "https://www.google.com/generate_204"

print(ttime(), "start")
while 1:
    running = True
    try:
        # http://127.0.0.1:8872/proxies
        sub_path = xor_encode_decode(
            b"EQ\x05\x06U[TD\x0bYUA\x02D\t\x07ZU[\x0c\x1c\x13\t^^",
            b"k2jh323kh542jkjh432",
        ).decode("utf-8")
        conf_path = Path.home().joinpath(sub_path)
        config_text = conf_path.read_text()
        m = re.search(r"m{1}i{1}x{1}e{1}d{1}-{1}p{1}o{1}r{1}t{1}: ?(\d+)", config_text)
        if not m:
            raise ValueError("no port found in config")
        proxy = f"http://127.0.0.1:{m[1]}"
        # try current proxy
        while check_current_proxy(proxy=proxy):
            n = 15
            for _ in range(n):
                time.sleep(1)
                print(n - _, end=" ", flush=True)
            continue
        print(flush=True)
        print(ttime(), "try to switch proxy", flush=True)
        m = re.search(r"s{1}e{1}c{1}r{1}e{1}t{1}:.*", config_text)
        if m:
            conf_path.write_text(
                re.sub(r"s{1}e{1}c{1}r{1}e{1}t{1}: *(.*)", "", config_text)
            )
            raise ValueError("restart your app")
        m = re.search(
            r"e{1}x{1}t{1}e{1}r{1}n{1}a{1}l{1}-{1}c{1}o{1}n{1}t{1}r{1}o{1}l{1}l{1}e{1}r{1}: *(.+)",
            config_text,
        )
        if not m:
            raise ValueError("serv addr not found %s" % config_text)
        api_url = "http://" + m[1]
        response = req.get(api_url + "/proxies")
        current_config = response.json()
        proxies = current_config["proxies"]
        nodes = {
            i["name"]
            for i in proxies.values()
            if i["type"] not in {"Selector", "Direct", "Reject"}
        }
        names = []
        for node in proxies["GLOBAL"]["all"]:
            if node in nodes:
                names.append(node)
        random.shuffle(names)
        pool = ThreadPoolExecutor(5)
        tasks = [test_node_delay(name) for name in names]
        results = []
        for task in as_completed(tasks):
            name, delay = task.result()
            print(ttime(), f"{name}: {delay} ms", flush=True)
            if delay < timeout:
                results.append((name, delay))
                payload = {"name": name}
                response = req.put(api_url + "/proxies/GLOBAL", json=payload)
                print(
                    ttime(),
                    f"Switched to node: {name} with delay: {delay}ms: {response.text}",
                    flush=True,
                )
                Path(__file__).touch()
                break
        else:
            raise ValueError("No nodes available")
    except KeyboardInterrupt:
        print(ttime(), "bye", flush=True)
        beep()
        break
    except Exception:
        print(ttime(), traceback.format_exc(), flush=True)
        # beep()
        # os.system("timeout 10")
        time.sleep(15)
    finally:
        running = False
