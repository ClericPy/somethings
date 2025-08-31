import re
import time
from queue import Empty, Queue
from threading import Thread

import FreeSimpleGUI as sg
import psutil


class ThreadController:
    current_regex: Queue[str] = Queue()
    current_selected = None
    last_regex = ""
    cache = ""


def get_tail(timeout=3):
    start = time.time()
    result = ""
    while time.time() - start < timeout:
        try:
            result = ThreadController.current_regex.get(timeout=1).strip()
        except Empty:
            if result:
                break
            continue
    return result


def find_procs():
    out = window.find_element("output")
    status = window.find_element("status")
    if not out or not status:
        raise RuntimeError("找不到输出或状态元素")
    current = ""
    while True:
        current = get_tail() or ThreadController.last_regex
        if not current:
            status.update(value="未输入正则")
            continue
        ThreadController.last_regex = current
        status.update(value=f"正在搜索: {current!r}")
        items = []
        for i in psutil.process_iter(["pid", "name", "cmdline"]):
            name = i.info["name"] or ""
            cmd = " ".join(i.info["cmdline"] or "")
            line = f"{i.pid:<8} | {name:<18} | {cmd}"
            if re.search(current, line, flags=re.IGNORECASE):
                items.append(line)
        items.sort(key=lambda x: (str(x.split(" | ", 1)[1]), int(x.split(" | ", 1)[0])))
        cache = "\n".join(items)
        if cache != ThreadController.cache:
            ThreadController.cache = cache
            out.update(values=items)
            status.update(value=f"搜索完成: {current!r} (更新 {len(items)} 条结果)")
        else:
            status.update(value=f"搜索完成: {current!r} ({len(items)} 条结果, 无更新)")
        current = ""


sg.theme("Default1")  # Add a touch of color
# All the stuff inside your window.
layout = [
    [
        sg.Text("输入正则："),
        sg.InputText("", key="regex", enable_events=True),
        sg.Button("Clear", key="clear"),
        sg.Text("", key="status"),
    ],
    # 表格里的行双击打印
    [sg.Listbox(values=[], size=(9999, 9999), key="output", enable_events=True)],
]
# Create the Window
window = sg.Window("Window Title", layout, resizable=True, size=(1080, 720))
# Event Loop to process "events" and get the "values" of the inputs
window.read(timeout=0)
window.maximize()
Thread(target=find_procs, daemon=True).start()
regex_input = window["regex"]
if not regex_input:
    raise RuntimeError("找不到输入元素")
while True:
    readed = window.read()
    if not readed:
        continue
    event, values = readed
    if (
        event == sg.WIN_CLOSED or event == "Cancel"
    ):  # if user closes window or clicks cancel
        break
    print("event, values:", event, values, flush=True)
    if event == "regex":
        reg = values["regex"]
        ThreadController.current_regex.put(reg)
    elif event == "clear":
        regex_input.update(value="")
        ThreadController.last_regex = ""
    elif event == "output":
        if values["output"]:
            # 两次点击时候是同一个选中的
            sel = values["output"][0]
            # print("选中:", sel, flush=True)
            pid, name = sel.split(" | ", 2)[:2]
            # 默认选中 yes
            yes = sg.popup_yes_no(
                "是否要杀死该进程？",
                f"{pid.strip()} - {name}",
                title="提示",
                keep_on_top=True,
            )
            print(yes, sel, flush=True)
            pid = int(sel.split(" | ", 1)[0])
            if yes == "Yes":
                try:
                    p = psutil.Process(pid)
                    p.terminate()
                    print(f"成功终止进程: {pid}", flush=True)
                except Exception as e:
                    print(f"终止进程失败: {pid}, {e}", flush=True)
            ThreadController.current_regex.put(ThreadController.last_regex)
window.close()
