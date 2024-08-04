import os
import random
import re
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

try:
    from morebuiltins.request import req
    from morebuiltins.utils import xor_encode_decode
except ImportError:
    import pip
    pip.main(["install", "morebuiltins"])
    from morebuiltins.request import req
    from morebuiltins.utils import xor_encode_decode


# 测试节点延迟
def test_node_delay(proxy_name):
    for _ in range(tries):
        response = req.get(
            api_url + f"/proxies/{quote(proxy_name)}/delay",
            params={"url": test_url, "timeout": timeout},
        )
        if "delay" not in response.json():
            delay = 9999
            break
        else:
            delay = response.json()["delay"]
    return proxy_name, delay


try:
    # api_url = "http://127.0.0.1:8872/"
    # http://127.0.0.1:8872/proxies
    sub_path = xor_encode_decode(
        b"EQ\x05\x06U[TD\x0bYUA\x02D\t\x07ZU[\x0c\x1c\x13\t^^", b"k2jh323kh542jkjh432"
    ).decode("utf-8")
    conf_path = Path.home().joinpath(sub_path)
    config_text = conf_path.read_text()
    m = re.search(r"secret:.*", config_text)
    if m:
        conf_path.write_text(re.sub(r"secret: *(.*)", "", config_text))
        raise ValueError("需要重启使接口生效")
    m = re.search(r"external-controller: *(.+)", config_text)
    if not m:
        raise ValueError("serv addr not found %s" % config_text)
    api_url = "http://" + m[1]
    timeout = 1500
    tries = 3
    test_url = "http://www.gstatic.com/generate_204"
    response = req.get(api_url + "/proxies")
    current_config = response.json()
    proxies = current_config["proxies"]
    pool = ThreadPoolExecutor(5)
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
    tasks = [pool.submit(test_node_delay, name) for name in names]
    results = []
    for task in as_completed(tasks):
        name, delay = task.result()
        print(f"{name}: {delay} ms", flush=True)
        if delay < timeout:
            results.append((name, delay))
            payload = {"name": name}
            response = req.put(api_url + "/proxies/GLOBAL", json=payload)
            print(
                f"Switched to node: {name} with delay: {delay}ms: {response.text}",
                flush=True,
            )
            break
    else:
        raise ValueError("No nodes available")
    os.system("timeout 3")
except Exception:
    traceback.print_exc()

    os.system("pause")
