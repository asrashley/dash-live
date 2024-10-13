import $ from 'jquery';

function updateHistory(ev) {
    const url = new URL(window.location);
    const path = $(ev.target).data('path');
    if (url.hash) {
      url.hash = path;
      history.replaceState({path: path,}, "", url);
    } else {
      url.hash = path;
      history.pushState({path: path,}, "", url);
    }
}

function expandPath() {
    const url = new URL(window.location);
    if (!url.hash) {
        return;
    }
    const items = url.hash.slice(1).split('.');
    for(let i = 0; i < items.length; ++i) {
      const path = items.slice(0, i + 1).join('.');
      const btn = $(`button[data-path="${path}"]`);
      if (btn.length) {
        btn.removeClass('collapsed');
        $(btn.data('target')).removeClass('collapse');
      }
    }
}

$('.atom-name').click(updateHistory);

expandPath();
