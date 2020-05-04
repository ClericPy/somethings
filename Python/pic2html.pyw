import re
import webbrowser
from functools import lru_cache
from html import escape
from pathlib import Path
from time import time
from tkinter import Tk
from tkinter.messagebox import askyesno, showerror
from typing import Dict, List
from hashlib import md5 as _md5

top = Tk()
dir_path_str = top.clipboard_get()
top.withdraw()
top.update()
TIMEOUT = 5
IMAGE_WIDTH = '80%'
valid_exts = {
    '.pcd', '.gif', '.jfif', '.raw', '.pcx', '.svg', '.pjpeg', '.pjp', '.eps',
    '.fpx', '.tga', '.cur', '.WMF', '.psd', '.tiff', '.png', '.ufo', '.tif',
    '.bmp', '.exif', '.ico', '.jpeg', '.jpg', '.ai', '.webp', '.cdr', '.dxf',
    '.apng'
}
# lazy load images
JS = '''
<script>
let ww = document.body.clientWidth
let wh = document.body.clientHeight
document.addEventListener('dblclick', on_dblclick);
function on_dblclick(e){
    if (e.srcElement.src){
        window.open(e.srcElement.src)
    }
}
const images = document.querySelectorAll('.lazy-load');
const config = {
    rootMargin: wh*3+'px 0px',
    threshold: 0.01
};
function preloadImage(el){
    el.setAttribute('src', el.getAttribute('data-src'))
    el.removeAttribute('data-src')
}
function onIntersection(entries) {
    entries.forEach(entry => {
        if (entry.intersectionRatio > 0) {
            observer.unobserve(entry.target);
            preloadImage(entry.target);
        }
    });
}
function range_change(){
    var value = document.getElementById('range').value ;
    document.getElementById('width').innerHTML = ' width: ' + value + '%';
    document.getElementById('new_width').innerHTML = '.pic{width:' + value + '%;}'
}
if (!('IntersectionObserver' in window)) {
    Array.from(images).forEach(image => preloadImage(image));
} else {
    observer = new IntersectionObserver(onIntersection, config);
    images.forEach(image => {
        observer.observe(image);
    });
}
document.querySelectorAll('h2').forEach(h2 => {
    h2.addEventListener('click', function () {
        location.hash="#name-list"
    })
});
</script>
'''
STYLE = '<style>html>body{background-color:#2c3e50;margin: 0 auto;width:100%;}hr{margin:2em 0 2em 0}img{width:100%;heigh:auto;}.pic{width:' + IMAGE_WIDTH + ';position:relative;}h2{text-align: center;width: 100%;padding: 1em;color: black;background-color: #ffffffd9}.path{position: absolute;color: white;padding: 2px;font-size: 0.6em;z-index: 2;bottom: 0;right: 0;background-color: #0e00006e;}a{color: white;text-decoration: none;margin: 1em;}ol{margin-left:30%;}h2:hover{cursor: pointer;}li{margin: 2px;}.article{display:flex;flex-direction: column;align-items: center;}</style>'


def md5(string, n=16, encoding="utf-8", skip_encode=False):
    """str(obj) -> md5_string"""
    todo = string if skip_encode else str(string).encode(encoding)
    if n == 16:
        return _md5(todo).hexdigest()
    elif isinstance(n, (int, float)):
        return _md5(todo).hexdigest()[(32 - n) // 2:(n - 32) // 2]
    elif isinstance(n, (tuple, list)):
        return _md5(todo).hexdigest()[n[0]:n[1]]


@lru_cache()
def get_relative_path(p: Path, root):
    result: List[Path] = []
    for i in range(10):
        result.insert(0, p)
        if p == root:
            break
        p = p.parent
    return root.joinpath(*result)


def run(dir_path: Path):
    global TIMEOUT
    root_string = dir_path.as_posix()
    container: Dict[str, list] = {}
    total = 0
    total_img = 0
    total_passed_secs = 0
    start_time = time()
    for i in dir_path.glob('**/*'):
        total += 1
        if not i.is_file():
            continue
        if i.suffix.lower() not in valid_exts:
            continue
        total_img += 1
        passed_secs = int(time() - start_time)
        if passed_secs > TIMEOUT:
            total_passed_secs += passed_secs
            is_continue = askyesno(
                'Confirm',
                f'Find more than {total_img} images in {total} files within {total_passed_secs} secs\nContinue?'
            )
            if not is_continue:
                showerror('Exit', 'Bye~')
                quit()
            start_time = time()
        parent = i.parent
        rp = get_relative_path(parent, dir_path)
        h2 = container.setdefault(rp.name, [])
        new_rp: Path = (rp / i.name).as_posix()
        src = str(new_rp).replace(root_string, '.')
        nums = re.findall(r'\d+', src)
        prefix = ''.join([num.rjust(5, '0') for num in nums])
        h2.append(f'{prefix}:{src}')
    if not container:
        raise FileNotFoundError(f'No pics? {valid_exts}')
    HTML = f'<html>{STYLE}<body><ol id="name-list"><input id="range" type="range" min="0" max="100" value="{IMAGE_WIDTH[:-1]}" step="1" oninput="range_change()"> <span id="width" style="color:white"> width: {IMAGE_WIDTH}</span>'
    for h2_str, srcs in container.items():
        srcs.sort()
        container[h2_str] = [src.split(':', 1)[1] for src in srcs]
        HTML += f'<li><a href="#{md5(h2_str)}">{escape(h2_str)} ({len(srcs)})</a></li>'
    HTML += '</ol><div class="articles">'
    for h2_str, srcs in container.items():
        HTML += f'<div class="article"><hr><h2 title="Click scoll to the top" id="{md5(h2_str)}">{escape(h2_str)}</h2><hr>'
        HTML += '\n'.join([
            f'''<div class="pic"><img class="lazy-load" title="double click to view" data-src="{src}" alt="Loading" /><div class="path">{src}</div></div>'''
            for src in srcs
        ])
        HTML += '</div>'
    HTML += f'</div></body><style id="new_width"></style>{JS}</html>'
    # max path length issue
    fp = dir_path / f'-{dir_path.name[:200-len(dir_path.as_posix())]}.html'
    with open(fp, 'w', encoding='u8') as f:
        f.write(HTML)
    webbrowser.open(fp.as_posix())


def main():
    try:
        dir_path = Path(dir_path_str)
        if not dir_path.is_dir():
            raise FileNotFoundError(f'{dir_path} is not valid dir path.')
        run(dir_path)
    except Exception as e:
        showerror('Error', repr(e))
    finally:
        top.destroy()


if __name__ == "__main__":
    main()
