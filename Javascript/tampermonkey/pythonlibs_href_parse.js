// ==UserScript==
// @name         pythonlibs_href_parse
// @namespace    https://github.com/ClericPy/somethings
// @version      0.7
// @author       Clericpy
// @description  try to take over the world!
// @match        https://www.lfd.uci.edu/~gohlke/pythonlibs/*
// @updateURL    https://raw.githubusercontent.com/ClericPy/somethings/master/Javascript/tampermonkey/pythonlibs_href_parse.js
// @downloadURL  https://raw.githubusercontent.com/ClericPy/somethings/master/Javascript/tampermonkey/pythonlibs_href_parse.js
// ==/UserScript==

(function () {
    'use strict';
    document.querySelectorAll('ul.pylibs > li > ul > li a').forEach(a => {
        var url = 'https://download.lfd.uci.edu/pythonlibs/archived/' + (decodeURI(a.textContent).replace(/‑/g, '-'))
        var tag = url.match(/.*-cp(27|34|35|36|37)-/)
        if (tag) {
            url = url.replace('/archived/', '/archived/cp' + tag[1] + '/')
        }
        a.setAttribute('href', url)
    });
})();
