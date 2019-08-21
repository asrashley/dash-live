$(document).ready(function(){
  'use strict';
  var pageState = {
    title: document.title,
    url: location.href,
    baseurl: location.href.split('#')[0],
  };
    
  function cycleOption(cell) {
    var sel, options, cur, i;
    
    sel = cell.find('select');
    options = cell.find('option');
    cur = sel.val();
    for (i=0; i < options.length; ++i) {
      if (options[i].value == cur) {
        sel.val(options[(i+1)%options.length].value);
        return;
      }
    }
  }

  function buildCGI() {
    var params;

    params = {};
    $('#buttons tbody .option select').each(function(idx, sel) {
      var val = $(sel).val();
      if (val) {
        params[sel.name] = val;
      }
    });
    if (params.drmloc) {
      if (params.drm && params.drm!=="drm=none") {
        params.drm += '-' + params.drmloc.split('=')[1];
      }
      delete params.drmloc;
    }
    return params;
  }

  function buildManifestURL() {
    var manifest, dest, url, params;

    dest = $('#dashurl');
    manifest = $('#buttons tbody .manifest.selected');
    if (!manifest) {
      dest.text('');
      dest.attr('href','');
      return;
    }
    url = manifest.data("uri");
    params = buildCGI();
    url += '?' + Object.values(params).join('&');
    dest.text(url);
    dest.attr('href',document.location.origin+url);
    if(window.history && typeof(history.pushState)==="function") {
      params.mpd = 'mpd=' + $('#buttons tbody .manifest.selected').data("filename");
      history.replaceState(pageState, $('#buttons tbody .manifest.selected').text(),
                           pageState.baseurl+'#'+Object.values(params).join('&'));
    }
  }

  function toggleActiveRow() {
    var cur = $('#buttons tbody .active')[0];

    $('#buttons .active').removeClass('active');
    if ($(cur).hasClass("manifest")) {
      $('#buttons .option, #buttons .option-key').addClass('active');
    } else {
      $('#buttons .manifest, #buttons .manifest-key').addClass('active');
    }
  }

  function playVideo() {
    var params;

    if (!$('#dashurl').attr("href")) {
      return;
    }
    params = buildCGI();
    params.mpd = 'mpd=' + $('#buttons tbody .manifest.selected').data("filename");
    document.location = '/video?'+Object.values(params).join('&');
  }

  $('body').on('keydown', function(ev){
    var row, active, params, p;

    if(ev.keyCode>=48 && ev.keyCode<=57){
      row = $('#row'+String.fromCharCode(ev.keyCode));
      if (!row) {
        return;
      }
      active = row.find(".active");
      if (!active) {
        return;
      }
      if (active.hasClass("manifest")) {
        $('#buttons .selected').removeClass('selected');
        active.addClass("selected");
        toggleActiveRow();
        params = active.data('params');
        for (p in params) {
          $('#buttons select[name="'+p+'"]').val(p+'='+params[p]);
        }
      } else {
        cycleOption(active);
      }
      buildManifestURL();
      return;
    }
    if (ev.keyCode==13) {
      /* enter */
      playVideo();
      return;
    }
    if (ev.keyCode==37 || ev.keyCode==39) {
      /* left or right cursor */
      toggleActiveRow();
      return;
    }
    console.log(ev.keyCode);
  });

  function init() {
    var params, i, p;
    $('a.manifest-title').on('click', function(ev) {
      var cell = ev.target;
      ev.preventDefault();
      $('#buttons .selected').removeClass('selected');
      while (cell.nodeName!="TD") {
        cell = cell.parentNode;
      }
      $(cell).addClass("selected");
      buildManifestURL();
      return false;
    });
    $('th.manifest, th.option').on('click', function(ev) {
      if ($(ev.target).hasClass('active')) {
        return;
      }
      toggleActiveRow();
    });
    $('#buttons tbody .option select').on('change', function(ev) {
      buildManifestURL();
    });
    $('#play-button').on('click', playVideo);
    if (/#/.test(document.location.href)) {
      params = document.location.href.split('#')[1];
      params = params.split('&');
      for(i=0; i<params.length; ++i) {
        p = params[i].split('=');
        if (p[0]=='mpd') {
          $('#buttons .selected').removeClass('selected');
          /* console.log('#buttons .manifest[data-filename="'+p[1]+'"]');
          $('#buttons .manifest[data-filename="'+p[1]+'"]').css('background-color','red'); */
          $('#buttons .manifest[data-filename="'+p[1]+'"]').addClass('selected');
        } else {
          /* $('#buttons select[name="'+p[0]+'"]').css('background-color','red'); */
          $('#buttons select[name="'+p[0]+'"]').val(params[i]);
        }
      }
      buildManifestURL();
    }
  }
  init();
});
