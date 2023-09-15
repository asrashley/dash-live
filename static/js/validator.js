$(document).ready(function(){
    'use strict';
    const socket = io();

    socket.on('connect', function() {
        socket.emit('cmd', {
	    method: 'hello',
	    payload: 'I\'m connected!'
	});
    });
 
    socket.on('hello', function(msg) {
	console.log(msg);
    });

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
	}
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
