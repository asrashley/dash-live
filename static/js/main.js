$(document).ready(function(){
  'use strict';
  var pageState = {
    title: document.title,
    url: location.href,
    baseurl: location.href.split('#')[0],
  };
  var cursor = { row:0, col:0, stream:0 };
    
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

  function moveCursor(direction) {
    var xpos, ypos, rows, cols;

    xpos = cursor.col;
    ypos = cursor.row;
    rows = $('#buttons tbody tr');
    cols = $('#buttons thead th');

    switch(direction) {
    case 'up':
      ypos -= 1;
      if (ypos < 0) {
        ypos = rows.length - 1;
      }
      break;
    case 'down':
      ypos = (ypos+1) % rows.length;
      break;
    case 'right':
	  if (cursor.row < (cursor.numRows-1)) {
		xpos = (xpos+1) % cols.length;
	  } else {
		cursor.stream = (cursor.stream+1) % pageState.streams.length;
		$('#play-button select').val(pageState.streams[cursor.stream].directory);
		buildManifestURL();
	  }
      break;
    case 'left':
	  if (cursor.row < (cursor.numRows-1)) {
		xpos -= 1;
		if (xpos < 0) {
          xpos = cols.length - 1;
		}
	  } else {
		cursor.stream--;
		if (cursor.stream<0) {
		  cursor.stream = pageState.streams.length - 1;
		  $('#play-button select').val(pageState.streams[cursor.stream].directory);
		  buildManifestURL();
		}
	  }
      break;
    }
    $('#buttons .cursor').removeClass('cursor');
    cols = $(rows[ypos]).find('td');
    $(cols[xpos % cols.length]).addClass('cursor');
    $('#buttons .active').removeClass('active');
	if (ypos == (rows.length)-1) {
	  $('#buttons tbody tr:last-child').addClass('active');
	} else {
	  $('#buttons tbody .manifest:nth-child('+(xpos+1)+'), #buttons tbody .option:nth-child('+(xpos+1)+')').addClass('active');
	}
    cursor.row = ypos;
	cursor.col = xpos;
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
    if (manifest.length == 0) {
      dest.text('');
      dest.attr('href','');
      $('#play-button').addClass('disabled');
      return;
    }
    url = manifest.data("uri").replace('{directory}', pageState.streams[cursor.stream].directory);
    params = buildCGI();
    url += '?' + Object.values(params).join('&');
    dest.text(url);
    dest.attr('href',document.location.origin+url);
    $('#play-button').removeClass('disabled');
    if(window.history && typeof(history.pushState)==="function") {
      params.mpd = 'mpd=' + $('#buttons tbody .manifest.selected').data("filename");
      history.replaceState(pageState, $('#buttons tbody .manifest.selected').text(),
                           pageState.baseurl+'#'+Object.values(params).join('&'));
    }
  }

  function playVideo() {
    var params;

    if (!$('#dashurl').attr("href")) {
      return;
    }
    params = buildCGI();
    params.mpd = 'mpd=' +
	  pageState.streams[cursor.stream].directory + '/' +
	  $('#buttons tbody .manifest.selected').data("filename");
    document.location = '/video?'+Object.values(params).join('&');
  }

  $('body').on('keydown', function(ev){
    var row, active, params, p;

    if(ev.keyCode>=48 && ev.keyCode<=57){
      row = $('#row'+String.fromCharCode(ev.keyCode));
      if (row.length===0) {
        return;
      }
      active = row.find(".active");
      if (active.length===0) {
        return;
      }
      if (active.hasClass("manifest")) {
        $('#buttons .selected').removeClass('selected');
        active.addClass("selected");
        params = active.data('params');
        for (p in params) {
          $('#buttons select[name="'+p+'"]').val(p+'='+params[p]);
        }
        moveCursor('right');
      } else {
        cycleOption(active);
      }
      buildManifestURL();
      return;
    }
    switch(ev.keyCode) {
    case 13: /* enter */
      active = $('#row'+cursor.row+' td:nth-child('+(cursor.col+1)+')');
      if (active.length===0) {
        /* cursor is on the "play video" row */
        playVideo();
        return;
      }
      if (cursor.col==0) {
        $('#buttons .selected').removeClass('selected');
        active.addClass("selected");
        params = active.data('params');
        for (p in params) {
          $('#buttons select[name="'+p+'"]').val(p+'='+params[p]);
        }
        buildManifestURL();
        moveCursor('right');
      } else {
        cycleOption(active);
      }
      break;
    case 80: /* 'p' */
      /* falls through */
    case 415: /* PLAY */
      playVideo();
      break;
    case 37: /* left */
	  moveCursor('left');
      break;
    case 38: /* up */
      moveCursor('up');
      break;
    case 39: /* right */
	  moveCursor('right');
      break;
    case 40: /* down */
      moveCursor('down');
      break;
    default:
      console.log(ev.keyCode);
      break;
    }
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
	$('#play-button select').on('change', function(ev) {
	  var i, val = $(ev.target).val();
	  for(i=0; i<pageState.streams.length; ++i) {
		if (pageState.streams[i].directory == val) {
		  cursor.stream = i;
		}
	  }
      buildManifestURL();
    });
    $('.play-icon').on('click', playVideo);

    if (typeof(Object.values)==="undefined") {
      Object.values = function(obj) {
        var k, rv = [];
        for (k in obj) {
          if (obj.hasOwnProperty(k)) {
            rv.push(obj[k]);
          }
        }
        return rv;
      }
      Object.keys = function(obj) {
        var k, rv = [];
        for (k in obj) {
          if (obj.hasOwnProperty(k)) {
            rv.push(k);
          }
        }
        return rv;
      }
    }
    
      cursor.numRows = $('#buttons tbody tr').length;
      cursor.numCols = $('#buttons tbody tr:first-child td').length;
      pageState.streams = [];
      $('#play-button option').each(function(idx, opt) {
	  opt = $(opt);
	  pageState.streams.push({title: opt.text(), directory: opt.val()});
          if (opt.val() == $(".play-select").val()) {
              cursor.stream = idx;
          }
      });
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
    moveCursor('');
    document.body.className += ' '+navigator.platform.toLowerCase();
  }
  init();
});
