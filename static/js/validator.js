$(document).ready(function(){
    'use strict';
    const socket = io();

    function updateDirectoryState(target) {
        if (target === null) {
            return;
        }
	if (target.checked) {
	    $('#model-prefix, #model-title').attr('disabled', false);
	    $('label[for="model-prefix"]').removeClass('disabled');
	    $('label[for="model-title"]').removeClass('disabled');
	} else {
	    $('#model-prefix, #model-title').attr('disabled', 'disabled');
	    $('label[for="model-prefix"]').addClass('disabled');
	    $('label[for="model-title"]').addClass('disabled');
	}
    }

    function checkInputValidity(target) {
	if (target.checkValidity()) {
	    $(target).addClass('is-valid').removeClass('is-invalid');
	} else {
	    $(target).removeClass('is-valid').addClass('is-invalid');
	}
    }

    /* socket.on('connect', function() {
    }); */

    function addLogMessage(msg) {
	const { level, text } = msg;
	const item = $('<p class="' + level + '">' + text + '</p>');
	$('#validator .results').append(item);
    }
    socket.on('log', addLogMessage);

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

    socket.on('manifest-validation', function(fields) {
	$('#manifest-form').addClass('was-validated');
	$('#manifest-form input').each((idx, elt) => {
	    const name = $(elt).attr('name');
	    if (fields[name]) {
		$(elt.parentElement).addClass('has-validation');
		$(elt).addClass('is-invalid');
		$(elt.parentElement).find('.invalid-feedback').text(fields[name]);
	    } else {
		$(elt.parentElement).removeClass('has-validation');
		$(elt.parentElement).find('.invalid-feedback').text('');
		$(elt).removeClass('is-invalid');
	    }
	});
	/* for (const [key, value] of Object.entries(fields)) {
	    const id = `model-${key}`;
	} */
    });

    socket.on('manifest-errors', function(errors) {
	errors.forEach(({ location, text }) => {
	    const [ start, end ] = location;
	    const err = $(`<p class="error-text">${text}</p>`);
	    const line = $(`#line-${start}`).append(err);
	    for(let i=start; i <= end; ++i) {
		$(`#line-${i}`).addClass('error');
	    }
	});
    });

    socket.on('script', function(data) {
	const { filename, title, prefix } = data;
	addLogMessage({
	    level: 'info',
	    text: `Installing ${filename}`
	});
	socket.emit('cmd', {
	    method: 'save',
            filename,
            prefix,
            title,
	});
    });

    $('#submit').on('click', (ev) => {
	ev.preventDefault();
	const form = document.getElementById('manifest-form');
	$('#manifest-form').removeClass('needs-validation');
	if (!form.checkValidity()) {
	    $('#manifest-form input').each((idx, elt) => {
		checkInputValidity(elt);
	    });
	    ev.stopPropagation();
	    addLogMessage({
		level: 'error',
		text: 'Form has errors'
	    });
	    $(form).removeClass('was-validated').addClass('is-invalid');
	    return;
	}

	const data = {
	    method: 'validate',
	};
	$(form).addClass('was-validated');
	$(form).serializeArray().forEach(function(item) {
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
    $('#model-save').on('change', (ev) => {
	updateDirectoryState(ev.target);
    });
    $('#manifest-form input').on('change', (ev) => {
	checkInputValidity(ev.target);
    });
    $('#manifest-form input').on('invalid', (ev) => {
	$(ev.target).removeClass('is-valid').addClass('is-invalid');
    });
    $('#manifest-form input').on('valid', (ev) => {
	$(ev.target).addClass('is-valid').removeClass('is-invalid');
    });
    updateDirectoryState(document.getElementById('model-save'));
});
