$(document).ready(function(){
    'use strict';
    const socket = io();

    /* socket.on('connect', function() {
    }); */

    socket.on('log', function(msg) {
	const { level, text } = msg;
	const item = $('<p class="' + level + '">' + text + '</p>');
	$('#validator .results').append(item);
    });

    socket.on('progress', function(data) {
	let { pct, text, finished } = data;
	if (pct !== undefined) {
	    const pct_str = `${pct}%`;
	    $('.progress-bar').css('width', pct_str).text(pct_str).attr('aria-valuenow', pct);
	}
	if (text !== undefined) {
	    $('.progress-text').text(text);
	}
	if (finished === true) {
	    $('.progress-bar').removeClass(['progress-bar-animated', 'bg-info']).addClass('bg-success');
	    socket.emit('cmd', {method: 'done'});
	}
    });

    socket.on('manifest', function(data) {
	$('#manifest-text').empty();
	data.text.forEach(function(txt, idx) {
	    const item = $(`<div class="manifest-line" id="line-${idx + 1}" />`);
	    item.append($(`<span class="line-num">${idx + 1}</span>`));
	    const text_elt = $('<pre class="text"></pre>');
	    text_elt.text(txt);
	    item.append(text_elt);
	    $('#manifest-text').append(item);
	});
    });

    socket.on('errors', function(errors) {
	errors.forEach(({ location, text }) => {
	    const [ start, end ] = location;
	    const err = $(`<p class="error-text">${text}</p>`);
	    const line = $(`#line-${start}`).append(err);
	    for(let i=start; i <= end; ++i) {
		$(`#line-${i}`).addClass('error');
	    }
	});
    });

    $('#submit').on('click', function(ev) {
	ev.preventDefault();
	const data = {
	    method: 'validate',
	};
	$('#manifest-form').serializeArray().forEach(function(item) {
	    data[item.name] = item.value;
	});
	$('#btn-validate').attr('disabled', 'disabled');
	$('#btn-cancel').attr('disabled', false);
	$('.progress-bar').addClass(['progress-bar-animated', 'bg-info']).removeClass('bg-success');
	$('.progress-bar').css('width', '0').text('0%').attr('aria-valuenow', '0');
	$('.progress-bar').css('visibility', 'visible');
	$('#validator .results').text('');
	socket.emit('cmd', data);
	return false;
    });
    $('#btn-cancel').on('click', function(ev) {
	ev.preventDefault();
	socket.emit('cmd', {method: 'cancel'});
	$('#btn-validate').attr('disabled', false);
	$('#btn-cancel').attr('disabled', 'disabled');
	return false;
    });
});
