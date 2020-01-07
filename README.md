
## Background

Store some scripts or snippets written by myself. Some GUI apps will build windows exe files.

## Downloads

https://github.com/ClericPy/somethings/releases

## Features

1. **Python**

   1. pydown (GUI, exe, pyw)

      > Simple downloader GUI for parsing special Websites.
      >
      > > pip install pyperclip requests[socks] PySimpleGUI

   2. proxy_speed (GUI, exe, pyw)

      > Check proxy speed for some cases.
      >
      > > pip install torequests pysocks PySimpleGUI

   3. PyinstallerUI  (TUI, py, python -m)

      > Terminal UI for PyInstaller.
      >
      > 1. pip install pyinstallerui -U
      >
      > 2. python -m pyinstallerui

2. **Javascript**
   1. tampermonkey (直接拖入 Chrome 油猴)

      1. 京东评论合并工具.js

         > *主要用途:*
         >
         > *1. 京东的评论每次点翻页太麻烦了, 需要找关键词的时候又不能搜索, 只好全复制出来了*
         >
         > *2. 偶尔需要语料*
         >
         > 
         >
         > *使用方法*
         >
         > *1. 加载网页以后, 在商品介绍 tab 位置会出现 [收集评论] 按钮, 点击, 等 1 秒*
         >
         > *2. 可以手动点 [采集], 一页页收集, 也可以配置好间隔秒数(默认2秒)点右边 checkbox 自动翻页*
         >
         > *3. 采集结束(或自行停止)后, 点击 [展示全部] 按钮, 则评论会在原来位置对多页合并*
         >
         > *4. 自行去噪过滤(可以通过选项, 也可以自己指定 css), 然后点击 [复制 TEXT] 即可复制到剪贴板*
         >
         > *5. emoji [文本] 点击可以打开 Ubuntu 的 pastebin 来粘贴刚才复制了的文本*

      2. dogedoge 搜索添加纯英文搜索词自动翻译, 百度 google 跳转.js
      
         > 如题, 就是添加点小按钮给多吉搜索和有道翻译. 纯英文检索会触发英译中, 中文检索词结尾带 空格+翻译 / 空格+英文 / 空格+英语 触发中译英
