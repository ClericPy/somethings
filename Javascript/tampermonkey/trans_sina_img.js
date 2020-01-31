// ==UserScript==
// @name         新浪图床防盗链
// @namespace    https://github.com/ClericPy/somethings
// @version      0.10
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
        var items = document.querySelectorAll('a, img')
        items.forEach(i => {
            let scode = i.outerHTML
            if (/:\/\/(ww|ws)\d+\.sinaimg\.cn\//g.test(scode)) {

            }
            i.outerHTML = scode.replace(/:\/\/(ww|ws)\d+\.sinaimg\.cn\//g, '://tva1.sinaimg.cn/')
        });
    }
    trans_img()
})();
