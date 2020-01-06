// ==UserScript==
// @name         京东评论加载
// @namespace    http://tampermonkey.net/
// @version      0.2
// @description  try to take over the world!
// @author       Clericpy
// @match        https://item.jd.com/*
// @grant        GM_setClipboard
// ==/UserScript==

/*

主要用途:
1. 京东的评论每次点翻页太麻烦了, 需要找关键词的时候又不能搜索, 只好全复制出来了
2. 偶尔需要语料

使用方法
1. 加载网页以后, 在商品介绍 tab 位置会出现 [收集评论] 按钮, 点击, 等 1 秒
2. 可以手动点 [采集], 一页页收集, 也可以配置好间隔秒数(默认2秒)点右边 checkbox 自动翻页
3. 采集结束(或自行停止)后, 点击 [展示全部] 按钮, 则评论会在原来位置对多页合并
4. 自行去噪过滤(可以通过选项, 也可以自己指定 css), 然后点击 [复制 TEXT] 即可复制到剪贴板
5. emoji [文本] 点击可以打开 Ubuntu 的 pastebin 来粘贴刚才复制了的文本

*/

(function () {
    'use strict';
    var pages = {}

    window.auto_pager_running = false
    var css_to_hidden = {}
    var custom_css_to_hidden = ''
    var button_style = `font: inherit; margin: 3px; overflow: visible; text-transform: none; -webkit-appearance: button; letter-spacing: 0.01em; zoom: 1; line-height: normal; white-space: nowrap; vertical-align: middle; text-align: center; cursor: pointer; -webkit-user-drag: none; user-select: none; box-sizing: border-box; font-size: 100%; padding: .5em 1em; color: rgba(0,0,0,.8); border: none transparent; background-color: #e6e6e6; text-decoration: none; border-radius: 2px; font-family: inherit;`

    var new_style = document.createElement("style");
    new_style.setAttribute('type', 'text/css')
    new_style.setAttribute('id', 'new_style')
    document.getElementsByTagName('body')[0].appendChild(new_style)

    function check_missing_pages() {
        var exist_page_nums = Object.keys(pages).sort()
        var max_num = exist_page_nums[exist_page_nums.length - 1]
        var missing_page_nums = []
        var i = 1
        while (i < max_num) {
            if (!(i in exist_page_nums)) {
                missing_page_nums.push(i)
            }
            i++;
        }
        if (missing_page_nums.length > 0) {
            var span = document.getElementById('commenter_state')
            span.innerText = '页码缺失: ' + missing_page_nums
        } else {
            var span = document.getElementById('commenter_state')
            span.innerText = ''
        }

    }


    function collect_dom_to_pages() {
        var node = document.querySelectorAll('#comment-0>div.comment-item')
        console.log(Object.keys(pages).length + ' pages: ' + Object.keys(pages))
        var page = document.querySelector('[class="ui-page-curr"]').innerText
        document.getElementById('commenter_crawl_button').innerText = '手动翻页 ' + page
        if (node.length > 0) {
            pages[page] = node
        }
        if (Object.keys(pages) > 0) {
            document.getElementById('commenter_show_button').style.display = 'inline-block'
        }
        check_missing_pages()
    }

    function show_pages() {

        var container = document.getElementById('comment-0')
        var backup_np_node = document.getElementsByClassName('com-table-footer')[0]
        container.innerHTML = ''
        Object.keys(pages).sort().forEach(function (key) {
            let items = pages[key]
            items.forEach(item => {
                container.appendChild(item)
            });
        });
        document.getElementById('commenter_copy_button').style.display = 'inline-block'
        document.getElementById('commenter_copy_text_button').style.display = 'inline-block'
        if (backup_np_node) {
            container.appendChild(backup_np_node)
        }
    }

    function copy_html() {
        var node = document.getElementById('comment-0')
        GM_setClipboard(node.innerHTML, 'text')
    }

    function copy_text() {
        let items = document.querySelectorAll('#comment-0>.comment-item')
        let text = ''
        items.forEach(item => {
            text += item.innerText.replace('\n', ' ') + '\n'
        });
        GM_setClipboard(text, 'text')
    }

    function auto_pager_with_interval() {
        collect_next_page()
    }

    function shutdown_auto_pager() {
        if (window.auto_pager_running) {
            window.clearInterval(window.current_autopager)
            window.auto_pager_running = false
        }
    }

    function auto_next_page() {
        shutdown_auto_pager()
        var commenter_auto_np_node = document.getElementById('commenter_auto_np')
        if (commenter_auto_np_node.checked) {
            window.auto_pager_running = true
            var interval = document.getElementById('commenter_auto_np_interval').value
            window.current_autopager = setInterval(() => {
                auto_pager_with_interval()
            }, interval * 1000);

        } else {
            shutdown_auto_pager()
            return
        }
    }

    function update_new_style() {
        let hidden_list = []
        Object.keys(css_to_hidden).forEach(key => {
            let value = css_to_hidden[key]
            if (value) {
                hidden_list.push(key)
            }
        });
        if (custom_css_to_hidden) {
            hidden_list.push(custom_css_to_hidden)
        }
        document.getElementById('new_style').innerHTML = hidden_list.join(',') + '{display: none;}\n'
    }

    function commenter_clear(checked, css_value) {
        css_to_hidden[css_value] = checked
        update_new_style()
    }

    function commenter_collect_comment() {

        var head = document.getElementsByClassName('filter-list')[0]
        var targetNode = document.getElementsByClassName('comment-item')[0]
        targetNode.addEventListener('DOMNodeRemoved', function () {
            collect_dom_to_pages()
        }, false);
        var hr = document.createElement("hr");
        head.appendChild(hr)


        var show_button = document.createElement("button");
        show_button.innerText = '展示全部'
        show_button.setAttribute('id', 'commenter_show_button')
        show_button.setAttribute('style', button_style)
        show_button.style.display = 'none'
        show_button.addEventListener('click', show_pages)
        head.appendChild(show_button)

        var copy_button = document.createElement("button");
        copy_button.innerText = '复制 HTML'
        copy_button.setAttribute('id', 'commenter_copy_button')
        copy_button.setAttribute('style', button_style)
        copy_button.style.display = 'none'
        copy_button.addEventListener('click', copy_html)
        head.appendChild(copy_button)

        var copy_text_button = document.createElement("button");
        copy_text_button.innerText = '复制 TEXT'
        copy_text_button.setAttribute('id', 'commenter_copy_text_button')
        copy_text_button.setAttribute('style', button_style)
        copy_text_button.style.display = 'none'
        copy_text_button.addEventListener('click', copy_text)
        head.appendChild(copy_text_button)


        var pastebin = document.createElement("a");
        pastebin.innerText = '📋'
        pastebin.href = 'https://paste.ubuntu.com/'
        pastebin.target = '_blank'
        pastebin.style.margin = '2px'
        head.appendChild(pastebin)

        var commenter_state = document.createElement("span");
        commenter_state.setAttribute('id', 'commenter_state')
        commenter_state.setAttribute('style', 'padding: 0.5em;')
        head.appendChild(commenter_state)

        var commenter_auto_np_interval = document.createElement("input");
        commenter_auto_np_interval.setAttribute('id', 'commenter_auto_np_interval')
        commenter_auto_np_interval.setAttribute('value', '2')
        commenter_auto_np_interval.setAttribute('size', 1)
        commenter_auto_np_interval.setAttribute('style', 'text-align: center;')
        head.appendChild(commenter_auto_np_interval)

        // var auto_page_label = document.createElement("span");
        // auto_page_label.innerText = '(s) 自动翻页'
        // auto_page_label.setAttribute = ('weight', 1000)
        // copy_text_button.style.margin = '3px'
        // head.appendChild(auto_page_label)

        // var commenter_auto_np = document.createElement("input");
        // commenter_auto_np.setAttribute('id', 'commenter_auto_np')
        // commenter_auto_np.setAttribute('type', 'checkbox')
        // commenter_auto_np.style.zoom = '120%'
        // head.appendChild(commenter_auto_np)

        // var crawl_button = document.createElement("button");
        // crawl_button.innerText = '手动翻页'
        // crawl_button.setAttribute('id', 'commenter_crawl_button')
        // crawl_button.setAttribute('style', button_style)
        // crawl_button.style.display = 'none'
        // crawl_button.addEventListener('click', collect_next_page)
        // head.appendChild(crawl_button)

        var filter_node = document.createElement("div")
        filter_node.setAttribute('id', 'commenter_filter')
        filter_node.style.display = 'inline'
        filter_node.innerHTML = `
<label for="commenter_auto_np">
    <span style="weight: 1000; margin: 3px;">(s) <b>自动翻页</b>:</span>
    <input type="checkbox" id="commenter_auto_np">
</label>
<button id="commenter_crawl_button" style="font-style: inherit; font-variant: inherit; font-weight: inherit; font-stretch: inherit; margin: 3px; overflow: visible; text-transform: none; -webkit-appearance: button; letter-spacing: 0.01em; zoom: 1; line-height: normal; white-space: nowrap; vertical-align: middle; text-align: center; cursor: pointer; -webkit-user-drag: none; user-select: none; box-sizing: border-box; font-size: 100%; padding: 0.5em 1em; color: rgba(0, 0, 0, 0.8); border: none transparent; background-color: rgb(230, 230, 230); text-decoration: none; border-radius: 2px; font-family: inherit; display: none;">手动翻页</button>

<hr><span><b>去噪:</b></span>
<label for="commenter_user"><input type="checkbox" checked name=".user-info" id="commenter_user">用户</label>
<label for="commenter_production"><input type="checkbox" checked name=".order-info>span:first-child" id="commenter_production">产品</label>
<label for="commenter_time"><input type="checkbox" checked name=".order-info>span:last-child" id="commenter_time">时间</label>
<label for="commenter_append"><input type="checkbox" checked name=".append-comment" id="commenter_append">追评</label>
<label for="commenter_append_time"><input type="checkbox" checked name=".append-comment>.append-time" id="commenter_append_time">追评时间</label>
<label for="commenter_other"><input type="checkbox" checked name=".comment-op,.user-level,.comment-star" id="commenter_other">冗余</label>
<label for="commenter_comment"><input type="checkbox" name=".comment-con" id="commenter_comment">文本</label>
<label for="commenter_comment_pics"><input type="checkbox" checked name=".pic-list" id="commenter_comment_pics">图片</label>
<label for="commenter_comment_video"><input type="checkbox" checked name=".J-video-view-wrap" id="commenter_comment_video">视频</label>
<label for="commenter_comment_tags"><input type="checkbox" checked name=".tag-list" id="commenter_comment_tags">标签</label>
<label for="commenter_seller_comment"><input type="checkbox" checked name=".recomment-con" id="commenter_seller_comment">卖家回复</label>
<label for="commenter_comment_custom">自定义:<input type="text" style="width:4em;" value="" placeholder="css" id="commenter_comment_custom"></label>
        `
        head.appendChild(filter_node)

        document.getElementById('commenter_crawl_button').addEventListener('click', collect_next_page)
        document.getElementById('commenter_auto_np').addEventListener('change', function () {
            auto_next_page()
        }, false)

        var filter_ids = ['commenter_user', 'commenter_production', 'commenter_time', 'commenter_append', 'commenter_append_time', 'commenter_other', 'commenter_comment', 'commenter_comment_pics', 'commenter_comment_video', 'commenter_comment_tags', 'commenter_seller_comment']
        filter_ids.forEach(eid => {
            let node = document.getElementById(eid)
            css_to_hidden[node.name] = node.checked
            update_new_style()
            node.addEventListener('change', function () {
                commenter_clear(this.checked, this.name)
            })
        });
        let commenter_comment_custom = document.getElementById('commenter_comment_custom')
        // commenter_comment_custom.addEventListener("keypress", function () {
        //     var value_length = this.value.length
        //     this.style.width = value_length * 5 + 'px'
        // })
        commenter_comment_custom.addEventListener('change', function () {
            custom_css_to_hidden = this.value
            this.title = this.value
            update_new_style()
        })
        collect_dom_to_pages()
        setTimeout(() => {
            document.getElementById('commenter_crawl_button').style.display = 'inline-block'
            collect_dom_to_pages()
        }, 1000);
    }

    function collect_next_page() {
        var np = document.getElementsByClassName('ui-pager-next')[0] || ''
        collect_dom_to_pages()
        setTimeout(() => {
            collect_dom_to_pages()
        }, 2000);
        if (np == '') {
            shutdown_auto_pager()
            var commenter_auto_np_node = document.getElementById('commenter_auto_np')
            commenter_auto_np_node.checked = false
            alert('已达最后一页')
            return false
        }
        np.click()

        return true
    }

    function setup_commenter_collect_comment() {
        if (document.getElementById('commenter_auto_np_interval')) {
            return
        }
        document.querySelector('[data-anchor="#comment"]').click()
        setTimeout(() => {
            commenter_collect_comment()
        }, 10);
    }

    function setup() {
        var tab = document.querySelector('#detail .tab-main>ul')
        var button = document.createElement("button");
        button.innerHTML = '<b>收集评论</b>'
        button.setAttribute('id', 'commenter_collect')
        button.setAttribute('style', button_style)
        button.addEventListener('click', setup_commenter_collect_comment)
        tab.appendChild(button)
    }


    window.onload = setup

    // Your code here...
})();
