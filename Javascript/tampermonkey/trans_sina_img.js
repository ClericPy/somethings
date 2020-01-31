// ==UserScript==
// @name         新浪图床防盗链
// @namespace    https://github.com/ClericPy/somethings
// @version      0.8
// @description  try to take over the world!
// @author       Clericpy
// @match        https://bh.sb/post/*
// @match        https://fast.v2ex.com/t/*
// @grant        none
// @updateURL    https://raw.githubusercontent.com/ClericPy/somethings/master/Javascript/tampermonkey/trans_sina_img.js
// @downloadURL  https://raw.githubusercontent.com/ClericPy/somethings/master/Javascript/tampermonkey/trans_sina_img.js
// ==/UserScript==

(function () {
    'use strict';

    function trans_img() {
        // var scode = document.documentElement.outerHTML
        // if (/:\/\/ww\d+\.sinaimg\.cn\//g.test(scode)) {
        //     scode = scode.replace(/:\/\/(ww|ws)\d+\.sinaimg\.cn\//g, '://tva1.sinaimg.cn/')
        //     document.write(scode)
        // }
        var items = document.querySelectorAll('[href*=".sinaimg.cn"]')
        items.forEach(i => {
            i.setAttribute('href', i.href.replace(/:\/\/(ww|ws)\d+\.sinaimg\.cn\//g, '://tva1.sinaimg.cn/'))
        });
        var items = document.querySelectorAll('[src*=".sinaimg.cn"]')
        items.forEach(i => {
            i.setAttribute('src', i.src.replace(/:\/\/(ww|ws)\d+\.sinaimg\.cn\//g, '://tva1.sinaimg.cn/'))
        });
    }
    document.addEventListener("DOMContentLoaded", function(event) {
        trans_img()
    });
})();
