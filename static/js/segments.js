$(document).ready(function(){
    'use strict';
    function updateHistory(ev) {
	var path, url;
	url = new URL(window.location);
	path = $(ev.target).data('path');
	if (url.hash) {
	    url.hash = path;
	    history.replaceState({path: path}, "", url);
	} else {
	    url.hash = path;
	    history.pushState({path: path}, "", url);
	}
    }
    function expandPath() {
	var i, url, btn, items, path;
	url = new URL(window.location);
	if (url.hash) {
	    items = url.hash.slice(1).split('.');
	    for(i = 0; i < items.length; ++i) {
		path = items.slice(0, i + 1).join('.');
		btn = $('button[data-path="' + path + '"]');
		if (btn.length) {
		    btn.removeClass('collapsed');
		    $(btn.data('target')).removeClass('collapse');
		}
	    }
	}
    }
    $('.atom-name').click(updateHistory);
    expandPath();
});
