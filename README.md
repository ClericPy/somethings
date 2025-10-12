## Background

Store some scripts or snippets written by myself. Some GUI apps will build windows exe files.

## Features

1. **Python**

   1. pydown (GUI, exe, pyw, archived)

      > Simple downloader GUI for parsing special Websites.
      
      > pip install pyperclip requests[socks] PySimpleGUI

   2. PyinstallerUI  (TUI, py, python -m)

      > Terminal UI for PyInstaller.
      
      > Steps:
      >
      > 1. pip install pyinstallerui -U
      > 2. python -m pyinstallerui
      
   3. Bookmarks checker

      > Steps:
      >
      > 1. export bookmark.html
      > 2. python bookmark_checker.py
      > 3. drag bookmark.html to terminal for the path
      > 4. wait for checking finished
      > 5. open the bookmark.html in the browser
      
   4. HTML image viewer

      > Find all the images in nested folders, generate the html file show them all.
      >
      > Features:
      >
      > 1. Recursively find pics in nested folders
      > 2. Fix the file name sorting issue like: 10.jpg < 2.jpg
      > 3. Auto fetch path from clipboard

   5. Video Deleter

      > Find all the images in nested folders, generate the html file show them all.
      >
      > Steps:
      >
      > 1. copy the folder path which includes video files
      > 2. python3 video_deleter.pyw

   6. NuitkaGUI

      > https://github.com/ClericPy/nuitka_simple_gui

   7. win32_dir_api.py
      1. Read a directory path from the clipboard, start a simple HTTP server, and open that directory in the browser.
      2. [win32_dir_api.exe](https://github.com/ClericPy/somethings/releases/tag/0.1)
         1. copy a directory path to clipboard
         2. run win32_dir_api.exe
         3. wait for the browser open the file list
         4. the cache dir will be created in the same dir as exe file, and removed when exit the program

2. **Javascript**
   1. tampermonkey (Chrome -> Tampermonkey -> Utilities -> Install from URL)

      1. jd_commenter.js

         > 主要用途:
         >
         > 1. 京东的评论每次点翻页太麻烦了, 需要找关键词的时候又不能搜索, 只好全复制出来了
         >
         > 2. 偶尔需要语料

      2. dogedoge_search_plus.js
      
         > 用途: doge 搜索添加纯英文搜索词自动翻译, 百度 google 跳转
         >
         > 纯英文检索会触发英译中, 中文检索词结尾带 空格+翻译 / 空格+英文 / 空格+英语 触发中译英

## Build

https://github.com/ClericPy/somethings/releases
