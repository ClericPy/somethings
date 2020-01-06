// ==UserScript==
// @name         doge search
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  try to take over the world!
// @author       Clericpy
// @match        https://www.dogedoge.com/results*
// @grant        GM_xmlhttpRequest
// @connect      dict.youdao.com

// ==/UserScript==

(function () {
    'use strict';
    var button_style = 'font-weight: 1000;color: #666; margin: 9px'
    var value = document.getElementById("search_form_input").value
    var node = document.createElement('a')
    node.setAttribute('href', 'https://www.baidu.com/s?wd=' + encodeURI(value))
    node.setAttribute('target', '_blank')
    node.setAttribute('style', button_style)
    node.innerText = '百度'
    document.getElementById("duckbar_static").appendChild(node);
    var node2 = document.createElement('a')
    node2.setAttribute('href', 'https://www.google.com/search?q=' + encodeURI(value))
    node2.setAttribute('target', '_blank')
    node2.setAttribute('style', button_style)
    node2.innerText = 'Google'
    document.getElementById("duckbar_static").appendChild(node2);
    if (!/.*[\u4e00-\u9fa5]+.*$/.test(value)) {
        var youdaoUrl = 'http://dict.youdao.com/jsonapi?xmlVersion=5.1&jsonversion=2&q=';

        GM_xmlhttpRequest({
            method: 'GET',
            url: youdaoUrl + encodeURI(value),
            headers: {
                'cookie': ''
            },
            onload: function (res) {
                var span = document.createElement('div')
                span.style = 'border: 1px dotted; padding: 1em;'
                var text = '<p>'
                for (const item of JSON.parse(res.responseText).ec.word[0].trs) {
                    text += item.tr[0].l.i[0] + '<br>'
                }
                text += '</p>'
                span.innerHTML = '<h4>翻译: </h4>' + text
                var links = document.getElementById('links')
                links.insertBefore(span, links.childNodes[0])
            },
            onerror: function (res) {

            }
        });
    }

})();
