"""forward.py 的最小自检：地址解析、URL 改写、透传/半关闭、并发上限、空闲超时、端到端。

只绑 loopback 与 OS 随机端口，不碰局域网地址，也不占用 3080。
跑法（在 Python/dsh-forward 目录里）：uv run --no-project test_forward.py
只用标准库，不需要 segno（那只在 forward.py --qr 时才用得上）。
"""

# 自检按仓库规范写成 assert 形式（见 ~/.dsh/AGENTS.md 第 4 节），S101 在这里是误报。
# ruff: noqa: S101

from __future__ import annotations

import contextlib
import http.client
import http.server
import os
import socket
import threading
import time
from typing import Any

# 本文件按脚本直接运行，脚本所在目录由解释器加入 sys.path；pyrefly 以仓库根为导入根，
# 解析不到同目录模块，故忽略这个诊断。
from forward import (  # pyrefly: ignore[missing-import]
    DEFAULT_PORT,
    URL_LINE_PATTERN,
    _ForwardServer,
    _open_browser,
    _parse_args,
    _splice,
    _valid_ipv4,
    build_access_url,
    is_newer,
    launch_web_gui,
    parse_target,
    parse_versions,
    pick_newest,
)

SOCKET_TIMEOUT_SECONDS = 5.0
THREAD_JOIN_SECONDS = 5.0
IDLE_PROBE_SECONDS = 0.5
TOKEN = "Ab_-" + "Z" * 39  # base64url 字符集，长度对齐 32 字节随机数编码后的 43
# 不是 dsh：拿它当"立刻退出的子进程"，用来验证提前退出时的快速失败。
WHERE_EXE = os.path.join(
    os.environ.get("SystemRoot", r"C:\Windows"), "System32", "where.exe"
)


def _recv_exactly(sock: socket.socket, size: int) -> bytes:
    """收满 size 字节，或在对端关闭时提前返回。"""
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            break
        chunks.extend(chunk)
    return bytes(chunks)


def _recv_until_closed(sock: socket.socket) -> bool:
    """读到对端关闭为 True；被 RST 也算关闭。"""
    try:
        return sock.recv(64) == b""
    except ConnectionResetError:
        return True


def check_parse_target() -> None:
    assert parse_target("127.0.0.1:3080") == ("127.0.0.1", 3080)
    assert parse_target("192.168.10.5:80") == ("192.168.10.5", 80)
    for bad in (
        "127.0.0.1",
        ":3080",
        "127.0.0.1:",
        "127.0.0.1:0",
        "127.0.0.1:70000",
        "127.0.0.1:abc",
    ):
        try:
            parse_target(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} 应当被拒绝")


def check_valid_ipv4() -> None:
    assert _valid_ipv4("192.168.10.5") == "192.168.10.5"
    assert _valid_ipv4("  10.0.0.1  ") == "10.0.0.1"
    assert _valid_ipv4("::1") is None
    assert _valid_ipv4("300.1.1.1") is None
    assert _valid_ipv4("") is None
    assert _valid_ipv4("nonsense") is None


def check_url_line_parsing() -> None:
    """只认真的 URL 行；同前缀的浏览器提示行不能被误匹配。"""
    gui_url = f"http://127.0.0.1:3080/?token={TOKEN}"
    match = URL_LINE_PATTERN.match(f"dsh web: {gui_url}")
    assert match is not None, "真 URL 行必须匹配"
    assert match.group(1) == gui_url

    with_lan = f"dsh web: {gui_url} (LAN: http://192.168.10.5:3080)"
    match = URL_LINE_PATTERN.match(with_lan)
    assert match is not None, "带 (LAN: …) 后缀的行必须匹配"
    assert match.group(1) == gui_url, "后缀不能被吃进 URL"

    hint = "dsh web: opening the default browser; pass --no-open to disable"
    assert URL_LINE_PATTERN.match(hint) is None, "提示行没有 http://，不该匹配"


def check_build_access_url() -> None:
    """token 原样保留，主机与端口换成转发器的，路径必须是 `/`。"""
    assert build_access_url(
        f"http://127.0.0.1:3080/?token={TOKEN}", "192.168.10.5", 3080
    ) == (f"http://192.168.10.5:3080/?token={TOKEN}")
    assert build_access_url(
        f"http://127.0.0.1:19387/?token={TOKEN}", "10.0.0.7", 4096
    ) == (f"http://10.0.0.7:4096/?token={TOKEN}")
    for bad in ("http://127.0.0.1:3080/", "http://127.0.0.1:3080/?x=1"):
        try:
            build_access_url(bad, "192.168.10.5", 3080)
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} 没有 token，应当被拒绝")


def check_splice() -> None:
    client_side, proxy_client = socket.socketpair()
    proxy_upstream, upstream_side = socket.socketpair()
    worker = threading.Thread(
        target=_splice, args=(proxy_client, proxy_upstream, 0.0), daemon=True
    )
    worker.start()
    try:
        for sock in (client_side, upstream_side):
            sock.settimeout(SOCKET_TIMEOUT_SECONDS)

        client_side.sendall(b"hello upstream")
        assert _recv_exactly(upstream_side, 14) == b"hello upstream"

        upstream_side.sendall(b"hello client")
        assert _recv_exactly(client_side, 12) == b"hello client"

        # 半关闭：客户端关写，上游必须先收到 EOF，而不是等连接整体关闭。
        client_side.shutdown(socket.SHUT_WR)
        assert upstream_side.recv(64) == b""
    finally:
        for sock in (client_side, upstream_side):
            with contextlib.suppress(OSError):
                sock.close()
        worker.join(timeout=THREAD_JOIN_SECONDS)
    assert not worker.is_alive(), "两端关闭后 _splice 应当退出"


class _TcpEchoServer:
    """极小的 TCP 回显服务，给不关心协议的用例当上游。"""

    def __init__(self) -> None:
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(8)
        self.port: int = self._listener.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            threading.Thread(target=self._echo, args=(conn,), daemon=True).start()

    @staticmethod
    def _echo(conn: socket.socket) -> None:
        try:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                conn.sendall(chunk)
        except OSError:
            return
        finally:
            with contextlib.suppress(OSError):
                conn.close()

    def close(self) -> None:
        with contextlib.suppress(OSError):
            self._listener.close()


def _start_forwarder(
    upstream_port: int, max_connections: int, idle_timeout: float
) -> _ForwardServer:
    forwarder = _ForwardServer(
        ("127.0.0.1", 0),
        ("127.0.0.1", upstream_port),
        max_connections=max_connections,
        idle_timeout=idle_timeout,
    )
    threading.Thread(target=forwarder.serve_forever, daemon=True).start()
    return forwarder


def _stop_forwarder(forwarder: _ForwardServer) -> None:
    forwarder.shutdown()
    forwarder.server_close()


def check_connection_cap() -> None:
    """并发上限为 1 时，第二条连接必须被立刻拒掉（不排进队列）。"""
    upstream = _TcpEchoServer()
    forwarder = _start_forwarder(upstream.port, max_connections=1, idle_timeout=0.0)
    port = forwarder.server_address[1]
    try:
        first = socket.create_connection(
            ("127.0.0.1", port), timeout=SOCKET_TIMEOUT_SECONDS
        )
        first.settimeout(SOCKET_TIMEOUT_SECONDS)
        try:
            first.sendall(b"ping")
            assert _recv_exactly(first, 4) == b"ping", (
                "第一条连接应当正常回显并占住名额"
            )

            second = socket.create_connection(
                ("127.0.0.1", port), timeout=SOCKET_TIMEOUT_SECONDS
            )
            second.settimeout(SOCKET_TIMEOUT_SECONDS)
            try:
                assert _recv_until_closed(second), "超出并发上限的连接应当被关闭"
            finally:
                second.close()
        finally:
            first.close()
    finally:
        _stop_forwarder(forwarder)
        upstream.close()


def check_idle_timeout() -> None:
    """空闲超过 idle_timeout 的连接必须被主动断开。"""
    upstream = _TcpEchoServer()
    forwarder = _start_forwarder(
        upstream.port, max_connections=8, idle_timeout=IDLE_PROBE_SECONDS
    )
    port = forwarder.server_address[1]
    try:
        client = socket.create_connection(
            ("127.0.0.1", port), timeout=SOCKET_TIMEOUT_SECONDS
        )
        client.settimeout(SOCKET_TIMEOUT_SECONDS)
        try:
            client.sendall(b"ping")
            assert _recv_exactly(client, 4) == b"ping"
            assert _recv_until_closed(client), "静默超过 idle_timeout 后应当被断开"
        finally:
            client.close()
    finally:
        _stop_forwarder(forwarder)
        upstream.close()


class _EchoPathHandler(http.server.BaseHTTPRequestHandler):
    """把请求路径原样回写为响应体，用于验证转发没有改动路径。"""

    seen: list[str] = []

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 的约定命名
        type(self).seen.append(self.path)
        body = self.path.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """静音访问日志；签名须与基类一致，故沿用遮蔽内建名的 `format`。"""


def check_end_to_end() -> None:
    """经真实转发器发一个带路径与查询串的请求，路径必须原样到达上游。

    注意上游也必须真的 serve_forever：只建对象不服务的话，请求会一直等不到响应，
    而收尾的 `shutdown()` 会永远阻塞（它等的事件只有 serve_forever 才会置位）。
    """
    upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _EchoPathHandler)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    forwarder = _start_forwarder(
        upstream.server_address[1], max_connections=8, idle_timeout=30.0
    )
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1", forwarder.server_address[1], timeout=SOCKET_TIMEOUT_SECONDS
        )
        try:
            connection.request("GET", "/deep/path?x=1&y=2")
            response = connection.getresponse()
            assert response.status == 200
            assert response.read() == b"/deep/path?x=1&y=2"
        finally:
            connection.close()
    finally:
        _stop_forwarder(forwarder)
        upstream.shutdown()
        upstream.server_close()
    assert _EchoPathHandler.seen == ["/deep/path?x=1&y=2"], _EchoPathHandler.seen


def check_version_selection() -> None:
    """stable 优先于同号 rc；rc 序号按数字比（rc.10 > rc.9）；alpha/beta 不参与。"""
    assert pick_newest(["0.1.7", "0.1.7-rc.2"]) == "0.1.7"
    assert pick_newest(["0.1.7-rc.2", "0.1.7-rc.10"]) == "0.1.7-rc.10", (
        "rc.10 必须大于 rc.9"
    )
    assert pick_newest(["0.1.6", "0.1.7-rc.2"]) == "0.1.7-rc.2"
    assert pick_newest(["0.1.9", "0.2.0-rc.1"]) == "0.2.0-rc.1"
    assert pick_newest(["0.1.7-rc.2", "0.1.8-alpha.1", "0.1.7-alpha.9"]) == "0.1.7-rc.2"
    assert pick_newest(["1.0.0-alpha.1", "1.0.0-beta.2"]) is None
    assert pick_newest([]) is None

    assert is_newer("0.2.0-rc.1", "0.1.7-rc.2") is True
    assert is_newer("0.1.7", "0.1.7-rc.2") is True, "stable 比同号 rc 新"
    assert is_newer("0.1.7-rc.2", "0.1.7") is False, "绝不降级"
    assert is_newer("0.1.7-rc.2", "0.1.7-rc.2") is False
    assert is_newer("nonsense", "0.1.7-rc.2") is False, "形状不认识就不动"
    assert is_newer("0.1.7-rc.2", "nonsense") is False


def check_version_parsing() -> None:
    """npm 在只有一个版本时给的是字符串而不是数组；格式不认识要返回 None。"""
    assert parse_versions('["0.1.0", "0.1.1"]') == ["0.1.0", "0.1.1"]
    assert parse_versions('"0.1.0"') == ["0.1.0"]
    assert parse_versions('{"a": 1}') is None
    assert parse_versions("not json") is None


def check_launch_fails_fast() -> None:
    """子进程提前退出时必须立刻报错，不能干等满 --launch-timeout。

    真实场景：端口已被另一个 dsh web 占用，新起的那个会秒退。这里用 where.exe 冒充，
    它同样秒退且不产出 URL 行。
    """
    assert os.path.isfile(WHERE_EXE), f"缺 {WHERE_EXE}"
    timeout = 20.0
    started = time.monotonic()
    try:
        launch_web_gui(WHERE_EXE, DEFAULT_PORT, "127.0.0.1", timeout)
    except OSError as error:
        assert "提前退出" in str(error), error
    else:
        raise AssertionError("where.exe 不该产出 URL 行")
    elapsed = time.monotonic() - started
    assert elapsed < timeout / 2, f"应当快速失败，实际等了 {elapsed:.1f} 秒"


def check_open_browser() -> None:
    """浏览器默认开、可用 --no-open-browser 关；交给它的必须是带 token 的本机 URL。"""
    assert _parse_args([]).open_browser is True
    assert _parse_args(["--open-browser"]).open_browser is True
    assert _parse_args(["--no-open-browser"]).open_browser is False

    seen: list[str] = []

    def recorder(url: str) -> bool:
        seen.append(url)
        return True

    local = f"http://127.0.0.1:3080/?token={TOKEN}"
    _open_browser(local, recorder)
    assert seen == [local], seen


def main() -> int:
    check_parse_target()
    check_valid_ipv4()
    check_url_line_parsing()
    check_build_access_url()
    check_version_selection()
    check_version_parsing()
    check_open_browser()
    check_launch_fails_fast()
    check_splice()
    check_connection_cap()
    check_idle_timeout()
    check_end_to_end()
    print("self-check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
