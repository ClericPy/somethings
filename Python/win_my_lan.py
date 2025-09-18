"Got my lan ip at windows"

import os

with os.popen("ipconfig") as f:
    items: list = []
    for line in f:
        indent = line.startswith(" ") or line.startswith("\t")
        line = line.strip()
        if line:
            if indent:
                last = items[-1]
                if line.startswith("IPv"):
                    last[line[:4]] = line.split(":", 1)[-1].strip()
                if "默认网关" in line:
                    gw = line.split(":", 1)[-1].strip()
                    if gw:
                        last["网关"] = gw
            else:
                items.append({})
    for i in items:
        if i.pop("网关", None):
            for k, v in i.items():
                print(f"{k}: {v}")
os.system("timeout 10")
