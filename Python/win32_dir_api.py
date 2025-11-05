import os
import socket
import sys
import webbrowser
from http.server import (
    BaseHTTPRequestHandler,
    SimpleHTTPRequestHandler,
    ThreadingHTTPServer,
    _get_best_family,
)
from pathlib import Path
from threading import Timer


def get_clipboard_text():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL

    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL

    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL

    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE

    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p

    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    CF_UNICODETEXT = 13

    # 检查格式
    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return ""

    # 打开剪贴板
    if not user32.OpenClipboard(None):
        return ""

    try:
        h_data = user32.GetClipboardData(CF_UNICODETEXT)
        if not h_data:
            return ""

        ptr = kernel32.GlobalLock(h_data)
        if not ptr:
            return ""

        try:
            # 读取以 null 结尾的宽字符字符串
            text = ctypes.wstring_at(ptr)
            return text
        finally:
            kernel32.GlobalUnlock(h_data)
    finally:
        user32.CloseClipboard()


# 新增：DownloadHTTPRequestHandler，所有文件请求都会带上 Content-Disposition 下载头
class DownloadHTTPRequestHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        # 先判断请求路径是否对应本地文件，如果是则准备下载文件名
        local_path = self.translate_path(self.path)
        self._download_filename = None
        if os.path.isfile(local_path):
            from urllib.parse import unquote

            name = os.path.basename(unquote(self.path))
            if not name:
                name = os.path.basename(local_path)
            self._download_filename = name
        return super().send_head()

    def end_headers(self):
        # 在结束 headers 之前注入 Content-Disposition（如果需要）
        if getattr(self, "_download_filename", None):
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{self._download_filename}"',
            )
        super().end_headers()

    def send_header(self, keyword, value):
        """Send a MIME header to the headers buffer."""
        if self.request_version != "HTTP/0.9":
            if not hasattr(self, "_headers_buffer"):
                self._headers_buffer = []
            self._headers_buffer.append(
                ("%s: %s\r\n" % (keyword, value)).encode("utf-8", "strict")
            )

        if keyword.lower() == "connection":
            if value.lower() == "close":
                self.close_connection = True
            elif value.lower() == "keep-alive":
                self.close_connection = False


def get_free_port(ip):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((ip, 0))
        return s.getsockname()[1]


def find_ip():
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
                    if "默认网关" in line or "Default Gateway" in line:
                        gw = line.split(":", 1)[-1].strip()
                        if gw:
                            last["gateway"] = gw
                else:
                    items.append({})
        ips = {}
        for i in items:
            if i.pop("gateway", None):
                for k, v in i.items():
                    # print(f"{k}: {v}")
                    ips[k] = v
        print(ips, flush=True)
        return ips


def test_server(
    HandlerClass=BaseHTTPRequestHandler,
    ServerClass=ThreadingHTTPServer,
    protocol="HTTP/1.0",
    port=8000,
    bind=None,
):
    """Test the HTTP request handler class.

    This runs an HTTP server on port 8000 (or the port argument).

    """
    ServerClass.address_family, addr = _get_best_family(bind, port)
    HandlerClass.protocol_version = protocol
    with ServerClass(addr, HandlerClass) as httpd:
        host, port = httpd.socket.getsockname()[:2]
        url_host = f"[{host}]" if ":" in host else host
        print(f"Serving HTTP on {host} port {port} (http://{url_host}:{port}/) ...")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received, exiting.")
            sys.exit(0)


def main():
    path = Path(get_clipboard_text())
    path = path if path.is_dir() else path.parent
    if not path.is_dir():
        raise ValueError("Clipboard does not contain a valid directory path")
    lan_ip = find_ip().get("IPv4")
    if not lan_ip:
        print("No lan ip found", flush=True)
        lan_ip = "127.0.0.1"
    port = get_free_port(lan_ip) or 8000
    url = f"http://{lan_ip}:{port}"
    print(url, flush=True)
    os.chdir(path)
    Timer(0.5, webbrowser.open, args=(url,)).start()
    test_server(DownloadHTTPRequestHandler, bind=lan_ip, port=port)


if __name__ == "__main__":
    main()
