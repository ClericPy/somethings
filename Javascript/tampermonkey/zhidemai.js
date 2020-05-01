// ==UserScript==
// @name         什么值得买抓取评论
// @namespace    https://github.com/ClericPy/somethings
// @version      0.1
// @description  什么值得买
// @author       Clericpy
// @match        http*://search.smzdm.com/*
// @grant        GM_xmlhttpRequest
// @connect      www.smzdm.com
// @connect      post.smzdm.com
// @updateURL    https://raw.githubusercontent.com/ClericPy/somethings/master/Javascript/tampermonkey/zhidemai.js
// @downloadURL  https://raw.githubusercontent.com/ClericPy/somethings/master/Javascript/tampermonkey/zhidemai.js
// ==/UserScript==

;(function () {
  unsafeWindow.crawler_interval = 1000
  unsafeWindow.stop_crawler = false
  function load_cmts(url, force, url_id) {
    if (force) {
      //   document.querySelector('.feed-pagenation').scrollIntoView({ behavior: 'smooth' })
      document.getElementById('show_node').innerHTML += '<hr>'
      unsafeWindow.stop_crawler = false
      let btn = document.getElementById(url_id)
      btn.innerText = '正在抓取'
      btn.disabled = true
    }
    if (unsafeWindow.stop_crawler) {
      let msg = '停止抓取: ' + document.querySelectorAll('#show_node>li').length + ' ×'
      document.getElementById('crawl_msg').innerHTML = msg
      let btn = document.getElementById(url_id)
      btn.innerText = '抓取评论'
      btn.disabled = false
      alert('抓取已停止')
      return
    }
    GM_xmlhttpRequest({
      method: 'GET',
      url: url,
      onload: function (resp) {
        var sub_doc = document.createElement('div')
        sub_doc.innerHTML = resp.responseText.trim()
        let cmts = sub_doc.querySelectorAll('#commentTabBlockNew>ul>li.comment_list')
        let show_node = document.getElementById('show_node')
        cmts.forEach((item) => {
          let text = item.querySelector('.comment_conBox>.comment_conWrap .comment_con [itemprop="description"]').innerText || ''
          let time = item.querySelector('div.time').innerText
          // console.log([text, time]);
          let newline = document.createElement('li')
          newline.innerHTML = `<span class="time">${time}</span><span>${text}</span>`
          show_node.appendChild(newline)
        })
        let msg = '正在抓取: ' + document.querySelectorAll('#show_node>li').length
        document.getElementById('crawl_msg').innerHTML = msg
        let btn = document.getElementById(url_id)
        btn.innerText = msg
        // 判断是否有下页
        let np = sub_doc.querySelector('li.pagedown a')
        if (np) {
          setTimeout(() => {
            load_cmts(np.href, false, url_id)
          }, unsafeWindow.crawler_interval)
        } else {
          let msg = '抓取完毕: ' + document.querySelectorAll('#show_node>li').length + ' √'
          document.getElementById('crawl_msg').innerHTML = msg
          btn.innerText = '抓取完毕'
        }
      },
    })
  }
  unsafeWindow.load_cmts = load_cmts
  function init() {
    let style = document.getElementsByTagName('style')[0]
    style.innerHTML += `
      #show_node>li>span.time{
          width: 7em;
          display:inline-block;
          text-align: center;
      }
      #show_node{
          margin-left: 2em;
      }
      #show_node>li{
          margin: 10px;
          list-style-type:decimal;
      }
      button.custom_cmts{
        display: inline-block;
        margin: 5px;
        zoom: 0.8;
        cursor: pointer;
        border: 1px solid #bbb;
        overflow: visible;
        font: bold 13px arial, helvetica, sans-serif;
        text-decoration: none;
        white-space: nowrap;
        background-image: -webkit-linear-gradient(top, rgba(255,255,255,1), rgba(255,255,255,0));
        transition: background-color .2s ease-out;
        background-clip: padding-box;
        border-radius: 3px;
        box-shadow: 0 1px 0 rgba(0, 0, 0, .3), 0 2px 2px -1px rgba(0, 0, 0, .5), 0 1px 0 rgba(255, 255, 255, .3) inset;
        text-shadow: 0 1px 0 rgba(255,255,255, .9);
        user-select: none;
        background-color: #eee;
        color: #555;
        padding: 4px 12px;
      }`
    document.querySelectorAll('#feed-main-list>li a.feed-btn-comment').forEach((item) => {
      if (item.title == '评论数 0') {
        return
      }
      let button = document.createElement('button')
      button.setAttribute('onclick', "load_cmts('" + item.href + "', true, '" + encodeURIComponent(item.href) + "')")
      button.innerText = '抓取评论'
      button.className = 'custom_cmts'
      button.title = '停止按钮在下方评论列表'
      button.id = encodeURIComponent(item.href)
      item.parentNode.appendChild(button)

      let button2 = document.createElement('button')
      button2.setAttribute('onclick', "document.querySelector('.feed-pagenation').scrollIntoView({behavior: 'smooth'})")
      button2.innerText = '查看结果'
      button2.className = 'custom_cmts'
      item.parentNode.appendChild(button2)
    })
    let temp_node = document.querySelector('.search-feedback')
    let head = document.createElement('h2')
    head.id = 'show_node_head'
    head.innerHTML = '<b>评论列表</b><br><span id="crawl_msg"></span>'
    temp_node.parentNode.insertBefore(head, temp_node)

    let stop_btn = document.createElement('button')
    stop_btn.setAttribute('onclick', '(function (){window.stop_crawler=true})()')
    stop_btn.innerHTML = '<b>停止</b>'
    stop_btn.className = 'custom_cmts'
    temp_node.parentNode.insertBefore(stop_btn, temp_node)

    let clear_btn = document.createElement('button')
    clear_btn.setAttribute('onclick', "(function (){document.getElementById('show_node').innerHTML='';document.getElementById('crawl_msg').innerHTML='已清空'})()")
    clear_btn.innerHTML = '<b>清空</b>'
    clear_btn.className = 'custom_cmts'
    temp_node.parentNode.insertBefore(clear_btn, temp_node)

    let show_node = document.createElement('ol')
    show_node.id = 'show_node'
    temp_node.parentNode.insertBefore(show_node, temp_node)
  }
  window.onload = init
})()
