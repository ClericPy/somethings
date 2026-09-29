# /// script
# requires-python = ">=3.10"
# dependencies = ["segno"]
# ///
"""把 loopback 上的 DSH Web GUI 按原端口、原路径转发到局域网（Windows）。

单文件工具：`uv run` 会按上面的 PEP 723 元数据自动备好 `segno`（唯一的第三方依赖，
且只有 `--qr` 用得上），所以不需要手动建 venv。`--no-project` 是必要的——本目录位于
一个带 `pyproject.toml` 的仓库里，不加它 uv 会试图用那个项目环境。

    uv run --no-project forward.py --check           # 只看计划，不绑端口
    uv run --no-project forward.py --launch --qr     # 起 GUI + 抓 token + 转发 + 出码
    uv run --no-project forward.py --target 127.0.0.1:3080   # 只转发已在跑的 GUI

## 为什么需要它

DSH 的 web 服务器 schema 只接受两个 host 字面量：

    host: z.union([z.const("127.0.0.1"), z.const("0.0.0.0")]).required()

而 `dsh web` 的 CLI 又硬拦 `0.0.0.0`，所以它无法原生绑到局域网地址，必须由本进程在
局域网地址上接客再透传给 loopback。

本进程做**纯 TCP 透传**，不改写 Host/Origin，因此 `dsh web` 启动时必须带
`--trusted-host <局域网IP>`：api-request-trust 栅栏要求 Host 是 loopback 或在
trustedHosts 内，而 LAN 字面量只在绑定 `0.0.0.0` 时才自动派生，loopback 绑定下只能靠
这个 flag，否则 /api 与 WebSocket 一律 403（实测：只换 Host 头即 401 → 403）。

注意设置类页面在 LAN 页面上仍不可用（`settings are unavailable in this browser`）：
客户端按**浏览器地址栏的 hostname** 判定 loopback，`--trusted-host` 管不到，所以启动时
会把本机那条 URL 一并打印出来。

## 抓 token 的依据

dsh 在 printUrl 打开时打印一行（app.asar:1017600）：

    dsh web: http://127.0.0.1:<port>/?token=<43 字符 base64url>[ (LAN: ...)]

同一个前缀还有一行**不带 URL** 的提示（`dsh web: opening the default browser; ...`），
所以正则必须要求 `http://`，否则会误匹配那一行。

## 版本同步（`--update-dsh`）

列出 npm 上所有版本，只在 stable(`x.y.z`) 与 rc(`x.y.z-rc.N`) 里挑最新的，比已装的新才
安装，绝不降级（alpha/beta 一律忽略；`rc.10` 按数字大于 `rc.9`）。与参照的
`dsh-web.bat` 有三处刻意不同：不静默安装 pnpm（只警告并继续用已装版本）；查询失败不中断
启动；当前版本用 `dsh -V` 读而不是 `pnpm list -g`（前者是"实际会跑的那个"的真相）。
"""

from __future__ import annotations

import argparse
import contextlib
import ipaddress
import json
import os
import re
import select
import shutil
import socket
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, cast
from urllib.parse import parse_qs, urlencode, urlsplit

# ── 常量：转发与探测 ──────────────────────────────────────────────────────────

DEFAULT_PORT = 3080
DEFAULT_TARGET_HOST = "127.0.0.1"
DEFAULT_MAX_CONNECTIONS = 64
DEFAULT_IDLE_TIMEOUT_SECONDS = 1800.0
DEFAULT_LAUNCH_TIMEOUT_SECONDS = 180.0
DEFAULT_QR_PNG = "dsh-qr.png"
LOOPBACK_TARGET_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
# 无线网卡的 MediaType 枚举名。用枚举名而不是界面别名（"WLAN"/"Wi-Fi"）或 ipconfig 的
# 本地化关键字，换系统语言不会失效。
WIRELESS_MEDIA_TYPE = "Native 802.11"
ROUTE_PROBE_ADDRESS = "8.8.8.8"
ROUTE_PROBE_PORT = 53
APIPA_PREFIX = "169.254."
BUFFER_BYTES = 65536
SELECT_POLL_SECONDS = 15.0
CONNECT_TIMEOUT_SECONDS = 10.0
POWERSHELL_TIMEOUT_SECONDS = 15.0
POWERSHELL_RELATIVE_PATH = os.path.join(
    "System32", "WindowsPowerShell", "v1.0", "powershell.exe"
)
EXIT_USAGE = 2
EXIT_BIND_FAILED = 1

# ── 常量：dsh 子进程与版本同步 ────────────────────────────────────────────────

URL_LINE_PATTERN = re.compile(r"^dsh web:\s+(https?://\S+)")
TERMINATE_TIMEOUT_SECONDS = 10.0
READY_POLL_SECONDS = 0.5
DSH_PACKAGE = "@deepseek-ai/dsh"
STABLE_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
RC_PATTERN = re.compile(r"^\d+\.\d+\.\d+-rc\.\d+$")
TRAILING_NUMBER_PATTERN = re.compile(r"(\d+)$")
VERSION_TIMEOUT_SECONDS = 30.0
CONFIG_TIMEOUT_SECONDS = 30.0
NPM_TIMEOUT_SECONDS = 90.0
PNPM_TIMEOUT_SECONDS = 600.0

# ── 常量：二维码 ──────────────────────────────────────────────────────────────

QR_ERROR_LEVEL = "m"
QR_PNG_SCALE = 6
QR_PNG_BORDER = 2


class _UsageError(Exception):
    """命令行用法错误，消息可直接展示给用户。"""


# ── 局域网 IP 探测 ────────────────────────────────────────────────────────────


def _valid_ipv4(text: str) -> str | None:
    """返回规范化后的 IPv4 字面量；非法输入或非 v4 返回 None。"""
    try:
        address = ipaddress.ip_address(text.strip())
    except ValueError:
        return None
    return str(address) if address.version == 4 else None


def _powershell_executable() -> str | None:
    """定位 powershell.exe 的绝对路径。

    用绝对路径而不是裸名字，避免 PATH 里的同名程序被优先执行。
    """
    candidate = os.path.join(
        os.environ.get("SystemRoot", "C:\\Windows"), POWERSHELL_RELATIVE_PATH
    )
    if os.path.isfile(candidate):
        return candidate
    return shutil.which("powershell")


def _wireless_ipv4() -> str | None:
    """取物理无线网卡的 IPv4，排除 APIPA 自分配地址。"""
    executable = _powershell_executable()
    if executable is None:
        return None
    script = (
        "Get-NetAdapter -Physical | "
        f"Where-Object MediaType -eq '{WIRELESS_MEDIA_TYPE}' | "
        "ForEach-Object { Get-NetIPAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv4 "
        "-ErrorAction SilentlyContinue } | "
        f"Where-Object {{ $_.IPAddress -notlike '{APIPA_PREFIX}*' }} | "
        "Select-Object -First 1 -ExpandProperty IPAddress"
    )
    try:
        completed = subprocess.run(  # noqa: S603 - 固定参数列表，未经 shell，无外部输入
            [executable, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=POWERSHELL_TIMEOUT_SECONDS,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in completed.stdout.splitlines():
        candidate = _valid_ipv4(line)
        if candidate is not None:
            return candidate
    return None


def _default_route_ipv4() -> str | None:
    """取默认路由出口网卡的 IPv4。UDP connect 不发包，只查本地选路。"""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect((ROUTE_PROBE_ADDRESS, ROUTE_PROBE_PORT))
        return _valid_ipv4(probe.getsockname()[0])
    except OSError:
        return None
    finally:
        probe.close()


def detect_bind_ip(explicit: str = "") -> str | None:
    """解析要绑定的局域网 IPv4：显式值 > 无线网卡 > 默认路由出口网卡。"""
    if explicit:
        return _valid_ipv4(explicit)
    return _wireless_ipv4() or _default_route_ipv4()


# ── 目标解析与 URL 拼装 ───────────────────────────────────────────────────────


def parse_target(text: str) -> tuple[str, int]:
    """把 host:port 解析成 (host, port)；不合法时抛 ValueError。"""
    host, separator, raw_port = text.rpartition(":")
    if not separator or not host or not raw_port:
        raise ValueError(f"目标地址必须是 host:port 形式：{text!r}")
    port = int(raw_port)
    if not 0 < port < 65536:
        raise ValueError(f"目标端口超出范围：{port}")
    return host, port


def find_dsh_command() -> str | None:
    """定位 dsh 可执行文件：PATH 优先，其次 pnpm 全局 bin。

    本机上 dsh 不在 PATH 里，只在 `%LOCALAPPDATA%\\pnpm\\bin\\dsh.cmd`。
    """
    found = shutil.which("dsh")
    if found is not None:
        return found
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidate = os.path.join(local_app_data, "pnpm", "bin", "dsh.cmd")
        if os.path.isfile(candidate):
            return candidate
    return None


def build_access_url(gui_url: str, bind_ip: str, listen_port: int) -> str:
    """把 GUI 打印的 loopback URL 换成局域网 URL，token 原样保留。

    路径必须是 `/`：dsh 只在 `GET /` 且恰好一个 token 参数时才做 token 交换。
    """
    tokens = parse_qs(urlsplit(gui_url).query).get("token")
    if not tokens:
        raise ValueError(f"URL 里没有 token 参数：{gui_url!r}")
    return f"http://{bind_ip}:{listen_port}/?{urlencode({'token': tokens[0]})}"


# ── TCP 透传 ──────────────────────────────────────────────────────────────────


def _pump(
    readable: list[socket.socket],
    active: set[socket.socket],
    peers: dict[socket.socket, socket.socket],
) -> bool:
    """把这一轮可读方向上的数据搬过去；返回 False 表示该收摊了。"""
    for source in readable:
        if source not in active:
            continue
        try:
            chunk = source.recv(BUFFER_BYTES)
        except OSError:
            return False
        if not chunk:
            # 单向 EOF：只半关闭对端对应方向，另一个方向继续搬。
            active.discard(source)
            with contextlib.suppress(OSError):
                peers[source].shutdown(socket.SHUT_WR)
            continue
        try:
            peers[source].sendall(chunk)
        except OSError:
            return False
    return True


def _splice(
    client: socket.socket, upstream: socket.socket, idle_timeout: float
) -> None:
    """双向搬运直到两端都关闭；单向 EOF 只半关闭对端对应方向。

    `idle_timeout` 为 0 表示不设上限。轮询间隔不会超过它，否则超时只能被粗粒度地
    发现。注意设得太短会掐断 GUI 的 WebSocket，浏览器随后需要重连。
    """
    poll_seconds = (
        SELECT_POLL_SECONDS
        if idle_timeout <= 0
        else min(SELECT_POLL_SECONDS, idle_timeout)
    )
    peers = {client: upstream, upstream: client}
    active = {client, upstream}
    last_activity = time.monotonic()
    try:
        while active:
            readable, _, _ = select.select(list(active), [], [], poll_seconds)
            if not readable:
                if (
                    idle_timeout > 0
                    and time.monotonic() - last_activity >= idle_timeout
                ):
                    return
                continue
            last_activity = time.monotonic()
            if not _pump(readable, active, peers):
                return
    finally:
        for sock in (client, upstream):
            with contextlib.suppress(OSError):
                sock.close()


class _Handler(socketserver.BaseRequestHandler):
    """把一个客户端连接接到上游，然后双向透传。

    并发名额在 `setup` 里取、`finish` 里还。之所以不覆写 socketserver 的
    `process_request`：那个签名接受 `socket | tuple[bytes, socket]`，窄化成 socket
    会破坏 LSP，类型检查器会直接判错。
    """

    _slot_held: bool = False

    def setup(self) -> None:
        server = cast(_ForwardServer, self.server)
        self._slot_held = server.acquire_slot()
        if not self._slot_held:
            with contextlib.suppress(OSError):
                self.request.close()

    def handle(self) -> None:
        if not self._slot_held:
            return
        server = cast(_ForwardServer, self.server)
        try:
            upstream = socket.create_connection(
                server.target, timeout=CONNECT_TIMEOUT_SECONDS
            )
        except OSError:
            return
        upstream.settimeout(None)
        self.request.settimeout(None)
        _splice(self.request, upstream, server.idle_timeout)

    def finish(self) -> None:
        if self._slot_held:
            cast(_ForwardServer, self.server).release_slot()


class _ForwardServer(socketserver.ThreadingTCPServer):
    """每连接一线程的转发服务，带并发上限与空闲回收。

    名额是在 worker 线程里取的，所以满员时线程仍会被创建、随即退出；被限制住的是
    **同时在传的连接数**，而不是瞬时的线程创建数。要连创建数一起压住就得上信号量 +
    accept 侧节流，那不值得。

    不设 allow_reuse_address：Windows 上 SO_REUSEADDR 会允许别的进程抢绑同一地址，
    这里宁可让重复启动明确失败。
    """

    allow_reuse_address = False
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        target: tuple[str, int],
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        idle_timeout: float = DEFAULT_IDLE_TIMEOUT_SECONDS,
    ) -> None:
        self.target = target
        self.idle_timeout = idle_timeout
        self._slots = threading.BoundedSemaphore(max_connections)
        super().__init__(address, _Handler)

    def acquire_slot(self) -> bool:
        """占用一个并发名额；满了返回 False（调用方负责关掉连接，不排队）。"""
        return self._slots.acquire(blocking=False)

    def release_slot(self) -> None:
        """归还并发名额。"""
        self._slots.release()


# ── dsh 子进程的启动与收尾 ────────────────────────────────────────────────────


def _taskkill_executable() -> str | None:
    """定位 taskkill.exe 的绝对路径；用绝对路径避免 PATH 里的同名程序被优先执行。"""
    root = os.environ.get("SystemRoot", "C:\\Windows")
    candidate = os.path.join(root, "System32", "taskkill.exe")
    if os.path.isfile(candidate):
        return candidate
    return shutil.which("taskkill")


def _kill_tree(process: subprocess.Popen[str]) -> None:
    """结束子进程及其整棵进程树。

    dsh 是 `.cmd` 包装器：直接 `terminate()` 只杀掉 cmd.exe，真正持有
    127.0.0.1:3080 的 node 会变成孤儿，下次启动就撞端口占用。Windows 上必须按进程树杀。
    """
    if process.poll() is not None:
        return
    executable = _taskkill_executable()
    if executable is None:
        process.terminate()
        return
    subprocess.run(  # noqa: S603 - 固定参数列表，未经 shell，只传本进程自己的 pid
        [executable, "/PID", str(process.pid), "/T", "/F"],
        capture_output=True,
        text=True,
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


@dataclass(slots=True)
class WebGui:
    """已启动的 dsh web 子进程及其带 token 的根 URL。"""

    process: subprocess.Popen[str]
    url: str

    def stop(self) -> None:
        """结束子进程及其整棵进程树，等不到就强杀。"""
        _kill_tree(self.process)
        try:
            self.process.wait(timeout=TERMINATE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=TERMINATE_TIMEOUT_SECONDS)


def _drain_output(stream: IO[str], found: list[str], ready: threading.Event) -> None:
    """持续抽干子进程输出，并在出现 URL 行时记下来。

    找到 URL 后仍要继续读：停读会让管道缓冲填满，反过来把子进程卡死。
    """
    for line in stream:
        sys.stdout.write(f"[dsh] {line}")
        sys.stdout.flush()
        if found:
            continue
        match = URL_LINE_PATTERN.match(line.strip())
        if match is not None:
            found.append(match.group(1))
            ready.set()


def launch_arguments(command: str, port: int, trusted_host: str) -> list[str]:
    """将要执行的 argv。`--check` 展示的与真正执行的是同一个来源。"""
    return [
        command,
        "web",
        "--no-open",
        "--port",
        str(port),
        "--trusted-host",
        trusted_host,
    ]


def launch_web_gui(
    command: str, port: int, trusted_host: str, timeout: float
) -> WebGui:
    """起 `dsh web --no-open`，等它打印出带 token 的 URL 行。"""
    process = subprocess.Popen(  # noqa: S603 - 固定参数列表，未经 shell；command 由调用方定位
        launch_arguments(command, port, trusted_host),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        bufsize=1,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    stream = process.stdout
    if stream is None:  # 上面传了 stdout=PIPE，正常不会发生
        _kill_tree(process)
        raise OSError("dsh 的 stdout 不可读")
    found: list[str] = []
    ready = threading.Event()
    threading.Thread(
        target=_drain_output, args=(stream, found, ready), daemon=True
    ).start()
    deadline = time.monotonic() + timeout
    while not ready.wait(READY_POLL_SECONDS):
        # 子进程提前退出就别干等满超时：最常见的原因是端口已被占用。
        if process.poll() is not None:
            raise OSError(
                f"dsh web 提前退出（退出码 {process.returncode}），没等到 URL 行；"
                f"端口 {port} 是否已被另一个 dsh web 占用？"
            )
        if time.monotonic() >= deadline:
            _kill_tree(process)
            raise TimeoutError(
                f"等 dsh 打印 URL 超时（{timeout:.0f} 秒）；用 --no-open 时它一定会打印"
            )
    return WebGui(process=process, url=found[0])


# ── dsh 版本同步 ──────────────────────────────────────────────────────────────


def _log(message: str) -> None:
    """打印并立刻刷出：stdout 被重定向时块缓冲会让日志迟迟不出现。"""
    print(message)
    sys.stdout.flush()


def _prerelease_number(prerelease: str) -> int:
    """取 `rc.<N>` 末尾的数字；取不到当 0。"""
    match = TRAILING_NUMBER_PATTERN.search(prerelease)
    return int(match.group(1)) if match else 0


def _sort_key(version: str) -> tuple[tuple[int, ...], int, int]:
    """排序键：核心数字 → stable 优先于预发布 → 预发布序号。

    `rc.10` 必须大于 `rc.9`（数字比较，不是字典序），`1.0.0` 必须大于 `1.0.0-rc.9`。
    """
    core, _, prerelease = version.partition("-")
    return (
        tuple(int(part) for part in core.split(".")),
        0 if prerelease else 1,
        _prerelease_number(prerelease),
    )


def _is_known_shape(version: str) -> bool:
    return (
        STABLE_PATTERN.match(version) is not None
        or RC_PATTERN.match(version) is not None
    )


def pick_newest(versions: Iterable[str]) -> str | None:
    """在 stable / rc 里挑最新；没有候选返回 None（alpha、beta 等一律不参与）。"""
    candidates = [version for version in versions if _is_known_shape(version)]
    return max(candidates, key=_sort_key, default=None)


def is_newer(candidate: str, current: str) -> bool:
    """candidate 是否严格新于 current；任一版本形状不认识就返回 False（不动）。"""
    if not _is_known_shape(candidate) or not _is_known_shape(current):
        return False
    return _sort_key(candidate) > _sort_key(current)


def parse_versions(raw: str) -> list[str] | None:
    """解析 `npm view <pkg> versions --json` 的输出。

    只有一个版本时 npm 给的是字符串而不是数组，所以要分开处理；格式不认识返回 None。
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, str):
        return [parsed]
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return None


def _run(
    argv: list[str], timeout: float, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(  # noqa: S603 - 固定参数列表，未经 shell；argv 都是本模块拼的
            argv,
            stdout=subprocess.PIPE,
            # 合并 stderr：失败原因（pnpm 的 ERR_PNPM_* 之类）都写在 stderr，不分流才看得到。
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=timeout,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None


def installed_version(dsh_command: str) -> str | None:
    """读当前实际会跑的 dsh 版本（`dsh -V`）；拿不到返回 None。"""
    done = _run([dsh_command, "-V"], VERSION_TIMEOUT_SECONDS)
    if done is None or done.returncode != 0:
        return None
    for line in done.stdout.splitlines():
        if line.strip():
            return line.strip()
    return None


def available_versions(npm_command: str) -> list[str] | None:
    """向 npm 查该包的全部版本；查询失败返回 None（区别于"查到了但为空"）。"""
    done = _run(
        [npm_command, "view", DSH_PACKAGE, "versions", "--json"], NPM_TIMEOUT_SECONDS
    )
    if done is None or done.returncode != 0:
        return None
    return parse_versions(done.stdout)


def global_bin_dir(pnpm_command: str) -> str | None:
    """问 pnpm 它的全局 bin 目录在哪；问不到就退回 pnpm 自己的默认约定。"""
    done = _run(
        [pnpm_command, "config", "get", "global-bin-dir"], CONFIG_TIMEOUT_SECONDS
    )
    if done is not None and done.returncode == 0:
        reported = [line.strip() for line in done.stdout.splitlines() if line.strip()]
        if reported and os.path.isdir(reported[-1]):
            return reported[-1]
    base = os.environ.get("PNPM_HOME") or os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "pnpm"
    )
    fallback = os.path.join(base, "bin")
    return fallback if os.path.isdir(fallback) else None


def _failure_detail(done: subprocess.CompletedProcess[str] | None) -> str:
    """从命令输出里取末尾几行当失败原因，别只留一个退出码。"""
    if done is None:
        return "进程起不来或超时"
    lines = [line.strip() for line in done.stdout.splitlines() if line.strip()]
    if not lines:
        return f"退出码 {done.returncode}，无输出"
    return " | ".join(lines[-4:])


def install_version(pnpm_command: str, version: str) -> tuple[bool, str]:
    """用 pnpm 全局安装指定版本，返回 (是否成功, 失败原因)。

    pnpm 在"全局 bin 目录不在 PATH"时会**直接拒绝**全局安装
    （`ERR_PNPM_GLOBAL_BIN_DIR_NOT_IN_PATH`，本机实测就是这个），所以先把该目录补进
    **子进程**的 PATH——只影响这一次调用，不动本进程环境。参照的 `dsh-web.bat` 也是同样
    的做法（启动时就 `set "PATH=%PNPM_HOME%\\bin;%PATH%"`）。
    """
    env = os.environ.copy()
    resolved = global_bin_dir(pnpm_command)
    if resolved is not None:
        env["PATH"] = resolved + os.pathsep + env.get("PATH", "")
    done = _run(
        [
            pnpm_command,
            "add",
            "-g",
            f"{DSH_PACKAGE}@{version}",
            "--config.dangerouslyAllowAllBuilds=true",
        ],
        PNPM_TIMEOUT_SECONDS,
        env=env,
    )
    if done is not None and done.returncode == 0:
        return True, ""
    return False, _failure_detail(done)


def _install_and_report(
    pnpm_command: str, dsh_command: str, current: str, target: str
) -> None:
    _log(f"[INFO] 更新 {DSH_PACKAGE} {current} -> {target} ...")
    installed, reason = install_version(pnpm_command, target)
    if installed:
        _log(f"[INFO] 更新完成，当前版本: {installed_version(dsh_command) or target}")
        return
    _log(f"[WARN] 更新失败，继续用已装版本。pnpm 说: {reason}")


def sync_dsh(dsh_command: str) -> None:
    """报告当前版本，并在 npm 有更新的 stable/RC 时更新。任何失败都只警告，不中断启动。"""
    current = installed_version(dsh_command)
    _log(f"[INFO] 当前 dsh 版本: {current or '未知'}")
    npm_command = shutil.which("npm")
    pnpm_command = shutil.which("pnpm")
    if npm_command is None or pnpm_command is None:
        _log("[WARN] 缺 npm 或 pnpm，跳过版本检查（不静默安装 pnpm）")
        return
    versions = available_versions(npm_command)
    if versions is None:
        _log("[WARN] 查不到 npm 上的版本列表（离线？），跳过更新")
        return
    target = pick_newest(versions)
    if target is None:
        _log("[WARN] npm 上没有可用的 stable/RC 版本，跳过更新")
        return
    _log(f"[INFO] npm 上最新 stable/RC: {target}")
    if current is None:
        _log("[WARN] 读不到当前版本，为避免误降级跳过安装")
        return
    if not is_newer(target, current):
        _log("[INFO] 已是最新（或本地更新），跳过安装")
        return
    _install_and_report(pnpm_command, dsh_command, current, target)


# ── 二维码 ────────────────────────────────────────────────────────────────────


def render_terminal(url: str) -> None:
    """往标准输出打 ANSI 半块二维码。

    segno 自带 PNG 编码，不需要 Pillow。75 字符的 DSH 访问 URL 落在 version 5 /
    error M，密度很低，手机很好扫。终端字体非等宽、或窗口太窄时可能扫不出来——那就用 PNG。
    """
    import segno  # 可选依赖：放在函数里，缺了它转发部分照常工作

    segno.make(url, error=QR_ERROR_LEVEL).terminal(compact=True)


def write_png(url: str, path: Path) -> None:
    """写一份 PNG 让看图器显示，比终端可靠。"""
    import segno  # 可选依赖，见 render_terminal

    segno.make(url, error=QR_ERROR_LEVEL).save(
        str(path), scale=QR_PNG_SCALE, border=QR_PNG_BORDER
    )


def open_png(path: Path) -> bool:
    """用系统默认看图器打开 PNG；不支持或启动失败时返回 False。"""
    starter = getattr(os, "startfile", None)
    if starter is None:
        return False
    try:
        starter(str(path))
    except OSError:
        return False
    return True


# ── CLI 编排 ──────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class _Plan:
    """解析完成后的执行计划；`gui` 非空时由本进程负责关掉它。"""

    bind_ip: str
    target: tuple[str, int]
    gui: WebGui | None
    local_url: str | None
    access_url: str | None
    launch_argv: list[str] | None


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="forward.py",
        description="把 loopback 上的 DSH Web GUI 按原端口、原路径转发到局域网。",
    )
    parser.add_argument(
        "--bind-ip", default="", help="绑定的局域网 IPv4；留空则自动取无线网卡"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"监听端口（默认 {DEFAULT_PORT}）",
    )
    parser.add_argument(
        "--target",
        default=f"{DEFAULT_TARGET_HOST}:{DEFAULT_PORT}",
        help=f"上游 host:port（默认 {DEFAULT_TARGET_HOST}:{DEFAULT_PORT}）",
    )
    parser.add_argument(
        "--max-connections",
        type=int,
        default=DEFAULT_MAX_CONNECTIONS,
        help=f"并发连接上限（默认 {DEFAULT_MAX_CONNECTIONS}）",
    )
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=DEFAULT_IDLE_TIMEOUT_SECONDS,
        help=f"空闲多少秒后断开（默认 {DEFAULT_IDLE_TIMEOUT_SECONDS:g}；0 = 不限）",
    )
    parser.add_argument(
        "--launch", action="store_true", help="自己起 dsh web，并抓它的 token URL"
    )
    parser.add_argument(
        "--update-dsh",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="启动前把全局 dsh 更新到 npm 上最新的 stable/RC（--no-update-dsh 关闭）",
    )
    parser.add_argument("--dsh", default="", help="dsh 可执行文件路径；留空则自动定位")
    parser.add_argument(
        "--launch-timeout",
        type=float,
        default=DEFAULT_LAUNCH_TIMEOUT_SECONDS,
        help=f"等 dsh 打印 URL 的秒数（默认 {DEFAULT_LAUNCH_TIMEOUT_SECONDS:g}）",
    )
    parser.add_argument(
        "--url", default="", help="已在运行的 GUI 的带 token URL，仅用于出二维码"
    )
    parser.add_argument("--qr", action="store_true", help="出二维码（终端 ANSI + PNG）")
    parser.add_argument(
        "--qr-png",
        default=DEFAULT_QR_PNG,
        help=f"PNG 落盘路径（默认 {DEFAULT_QR_PNG}）",
    )
    parser.add_argument(
        "--qr-open",
        action="store_true",
        help="额外用系统看图器弹出 PNG（默认只用终端那张）",
    )
    parser.add_argument(
        "--open-browser",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="就绪后用默认浏览器打开本机 URL（--no-open-browser 关闭；--check 不打开）",
    )
    parser.add_argument(
        "--check", action="store_true", help="只打印解析结果，不绑定端口"
    )
    return parser.parse_args(argv)


def _launch_gui(
    args: argparse.Namespace, bind_ip: str, target: tuple[str, int]
) -> tuple[WebGui, list[str]]:
    """起 `dsh web` 并返回子进程与将要执行的 argv。"""
    if target[0] not in LOOPBACK_TARGET_HOSTS:
        raise _UsageError(f"--launch 只支持上游为 loopback，当前上游是 {target[0]}")
    command = args.dsh or find_dsh_command()
    if command is None:
        raise _UsageError(
            "没找到 dsh；用 --dsh 指定绝对路径，例如 --dsh %LOCALAPPDATA%\\pnpm\\bin\\dsh.cmd"
        )
    if args.update_dsh:
        # 必须在拉起之前：更新的是将要被执行的那份全局安装。
        sync_dsh(command)
    argv = launch_arguments(command, target[1], bind_ip)
    try:
        gui = launch_web_gui(command, target[1], bind_ip, args.launch_timeout)
    except (OSError, TimeoutError) as error:
        raise _UsageError(f"启动 dsh web 失败：{error}") from error
    return gui, argv


def _validate_args(args: argparse.Namespace) -> None:
    """把明显非法的参数在绑定端口之前挡掉。"""
    if not 0 < args.port < 65536:
        raise _UsageError(f"监听端口超出范围：{args.port}")
    if args.max_connections < 1:
        raise _UsageError(f"--max-connections 必须 ≥ 1：{args.max_connections}")
    if args.idle_timeout < 0:
        raise _UsageError(f"--idle-timeout 不能为负：{args.idle_timeout}")
    if args.update_dsh and not args.launch:
        raise _UsageError(
            "--update-dsh 只在 --launch 下有意义（它更新的是被拉起的那份 dsh）"
        )


def _access_urls(
    args: argparse.Namespace, bind_ip: str, gui: WebGui | None
) -> tuple[str | None, str | None]:
    """算出 (本机 URL, 局域网 URL)；没有 token 来源时两个都是 None。

    本机那条必须一并给出：设置类页面只在 loopback 页面上可用（客户端按浏览器地址栏的
    hostname 判定，请求头说了不算），而 `--trusted-host` 只解决 /api 的信任栅栏。
    """
    source = gui.url if gui is not None else args.url
    if not source:
        return None, None
    return source, build_access_url(source, bind_ip, args.port)


def _build_plan(args: argparse.Namespace) -> _Plan:
    """把参数解析成执行计划；任何失败都在绑定端口之前报出来，且不留子进程。"""
    bind_ip = detect_bind_ip(args.bind_ip)
    if bind_ip is None:
        raise _UsageError(
            "没能解析出局域网 IPv4；用 --bind-ip 显式指定，例如 --bind-ip 192.168.1.5"
        )
    _validate_args(args)
    try:
        target = parse_target(args.target)
    except ValueError as error:
        raise _UsageError(str(error)) from error

    gui: WebGui | None = None
    launch_argv: list[str] | None = None
    try:
        if args.launch:
            gui, launch_argv = _launch_gui(args, bind_ip, target)
        local_url, access_url = _access_urls(args, bind_ip, gui)
    except (ValueError, _UsageError) as error:
        if gui is not None:
            gui.stop()
        raise _UsageError(str(error)) from error
    return _Plan(
        bind_ip=bind_ip,
        target=target,
        gui=gui,
        local_url=local_url,
        access_url=access_url,
        launch_argv=launch_argv,
    )


def _print_plan(plan: _Plan, args: argparse.Namespace) -> None:
    print(f"监听   http://{plan.bind_ip}:{args.port}/")
    print(f"转发到 http://{plan.target[0]}:{plan.target[1]}/")
    print(
        f"并发上限 {args.max_connections}；空闲上限 {args.idle_timeout:g} 秒（0 = 不限）"
    )
    if plan.launch_argv is not None:
        print(f"已启动 {' '.join(plan.launch_argv)}")
    print()
    if plan.access_url is not None:
        print("手机访问（局域网，token 已带上，别外传）：")
        print(f"  {plan.access_url}")
        print()
        print("本机访问（设置/模型页只在 loopback 页面上可用，改配置用这条）：")
        print(f"  {plan.local_url}")
    else:
        print("两端都要对上，缺一不可：")
        print("  1) 启动 GUI 时声明信任，否则 /api 与 WebSocket 一律 403：")
        print(f"       dsh web --trusted-host {plan.bind_ip} --no-open")
        print("  2) 其他机器访问时把 dsh 打印的 URL 主机名换掉，token 原样保留：")
        print(f"       http://{plan.bind_ip}:{args.port}/?token=<dsh 打印的 token>")
    print()
    print(
        "注意：不要改成绑 0.0.0.0 —— 那会连 loopback 流量一起抢走，转发到同端口形成自环。"
    )
    # stdout 被重定向时是块缓冲，不主动 flush 的话这段横幅可能一直不出现。
    sys.stdout.flush()


def _emit_qr(plan: _Plan, args: argparse.Namespace) -> int:
    if plan.access_url is None:
        print(
            "[错误] --qr 需要 token URL：加 --launch，或用 --url 手动给出",
            file=sys.stderr,
        )
        return EXIT_USAGE
    png_path = Path(args.qr_png).resolve()
    try:
        render_terminal(plan.access_url)
        write_png(plan.access_url, png_path)
    except ImportError as error:
        print(
            f"[错误] 出二维码需要 segno（uv run 会自动装上；手动跑就 pip install segno）：{error}",
            file=sys.stderr,
        )
        return EXIT_USAGE
    print(f"二维码已写入 {png_path}")
    if args.qr_open:
        if open_png(png_path):
            print("已交给默认看图器打开；扫不出来就放大窗口，或直接扫终端里那张。")
        else:
            print("（没能自动打开图片，请手动打开上面这个路径）")
    sys.stdout.flush()
    return 0


def _open_browser(url: str, opener: Callable[[str], bool] = webbrowser.open) -> None:
    """用系统默认浏览器打开本机 URL。

    开的是**带 token** 那条：裸 `http://127.0.0.1:<port>/` 会因为缺凭据返回 401。
    `opener` 可注入，自检时用它替掉真实的开窗动作。
    """
    try:
        opened = opener(url)
    except webbrowser.Error:
        opened = False
    if opened:
        print("已用默认浏览器打开本机地址。")
    else:
        print("（没能自动打开浏览器，请手动访问上面那条本机 URL）")
    sys.stdout.flush()


def _serve(plan: _Plan, args: argparse.Namespace) -> int:
    try:
        server = _ForwardServer(
            (plan.bind_ip, args.port),
            plan.target,
            max_connections=args.max_connections,
            idle_timeout=args.idle_timeout,
        )
    except OSError as error:
        print(f"[错误] 绑定 {plan.bind_ip}:{args.port} 失败：{error}", file=sys.stderr)
        print(
            "       端口被占用就换 --port，并同步改 --trusted-host 的端口部分。",
            file=sys.stderr,
        )
        return EXIT_BIND_FAILED
    print("\n已就绪，Ctrl+C 停止。")
    # 绑端口成功了才开浏览器，这样"启动成功"才名副其实。
    if args.open_browser and plan.local_url is not None:
        _open_browser(plan.local_url)
    try:
        with server:
            server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        plan = _build_plan(args)
    except _UsageError as error:
        print(f"[错误] {error}", file=sys.stderr)
        return EXIT_USAGE
    try:
        _print_plan(plan, args)
        if args.qr:
            code = _emit_qr(plan, args)
            if code != 0:
                return code
        if args.check:
            print("\n（--check：未绑定端口）")
            return 0
        return _serve(plan, args)
    finally:
        if plan.gui is not None:
            plan.gui.stop()


if __name__ == "__main__":
    raise SystemExit(main())
