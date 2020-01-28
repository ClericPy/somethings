# -*- coding: utf-8 -*-
# pip install beautifulsoup4 requests
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
    'Referer': '',
}
session = requests.Session()
LEFT = 0
update_node_lock = Lock()
root = None


def check_request(url):
    result = (False, 'unknown')
    if not url:
        return result
    r = None
    try:
        r = session.head(
            url, timeout=3, allow_redirects=1, headers=headers, verify=0)
        if r.status_code == 405:
            r = session.get(url, timeout=3, stream=1, headers=headers, verify=0)
            next(r.iter_content(1))
        result = (r.ok, r.status_code)

    except requests.RequestException as e:
        result = (False, e.__class__.__name__)
    finally:
        if r:
            r.close()
        return result


def check_a(a):
    global LEFT
    href = a.get('href')
    ok, status = check_request(href)
    with update_node_lock:
        if href:
            a['title'] = status
            a['target'] = '_blank'
            if ok:
                a['style'] = 'color: green'
            else:
                a['style'] = 'color: red'
            status_string = f'[{status}] {urlparse(href).netloc}'
            if a.get('has_status'):
                new_tag = a.parent.a
                new_tag.string = status_string
            else:
                new_tag = root.new_tag(
                    "a",
                    _name='status',
                    target='_blank',
                    class_='status_link',
                    style='width:20em;display:inline-block;border: 0px solid #000;',
                    href=f'chrome://bookmarks/?q={quote_plus(href)}')
                new_tag.string = status_string
                a.insert_before(new_tag)
                a['has_status'] = 1
        LEFT -= 1
        print(LEFT, end=' ', flush=1)


def main():
    global LEFT, root
    while 1:
        file_path = input('Input the bookmark.html path:')
        # file_path = r'C:\Users\ld\Desktop\bookmarks_2020_1_28.html'
        path = Path(file_path)
        if not path.is_file():
            print('File not exist')
            continue
        with open(path, encoding='u8') as f:
            scode = f.read()
            break
    root = BeautifulSoup(scode, features=None)
    a_nodes = [a for a in root.select('a') if a.get('add_date')]
    LEFT = len(a_nodes)
    with ThreadPoolExecutor(100) as pool:
        pool.map(check_a, a_nodes)
    path.write_text(str(root), encoding='u8')


if __name__ == "__main__":
    main()
