import $ from 'jquery';
import { enableTooltips } from './tooltips.js';

function addClickListeners() {
    $('#keys .add-key').on('click', addKey);
    $('#keys .delete-key').on('click', deleteKey);
    $('#streams .add-stream').on('click', addStream);
    $('#streams .delete-stream').on('click', deleteStream);
    $('#edit-model .delete-stream').on('click', deleteStream);
    $('#media-files .delete-file').on('click', deleteFile);
    $('#media-files .btn-index').on('click', indexFile);
    $("#upload-form .submit").on('click', uploadFile);
    $('#dialog-box .btn-close').on('click', closeDialog);
}

function removeClickListeners() {
    $('#keys .add-key').off('click', addKey);
    $('#keys .delete-key').off('click', deleteKey);
    $('#streams .add-stream').off('click', addStream);
    $('#streams .delete-stream').off('click', deleteStream);
    $('#edit-model .delete-stream').off('click', deleteStream);
    $('#media-files .delete-file').off('click', deleteFile);
    $('#media-files .btn-index').off('click', indexFile);
    $("#upload-form .submit").off('click', uploadFile);
    $('#dialog-box .btn-close').off('click', closeDialog);
}

function reloadContent() {
    $.ajax({
        url: `${document.location}?fragment=1`,
        method: 'GET',
    }).done((result) => {
        removeClickListeners();
        $('#media-management').parent().html(result);
        addClickListeners();
    });
}

function addKey(ev) {
    const $row = $(ev.target).parents('tr');
    const kid = $row.find('input[name="kid"]').val();
    const key = $row.find('input[name="key"]').val();
    const csrf_token = $('#keys').data('csrf');
    $row.find('.btn').attr("disabled", true);
    $('#keys .error').text('');
    $.ajax({
        url: '/key',
        method: 'PUT',
        data: {
          kid,
          key,
          csrf_token,
        },
        dataType: 'json',
    }).done((result) => {
        if (result.error) {
            $('#keys .error').text(result.error);
            return;
        }
        if (result.csrf_token) {
            $('#keys').data('csrf', result.csrf_token);
        }
        reloadContent();
    });
}

function deleteKey(ev) {
    const $row = $(ev.target).parents('tr');
    const kid = $row.find('.kid').text();
    if (!kid) {
        return;
    }
    const csrf = $('#keys').data('csrf');
    $('#keys .error').text('');
    $.ajax({
        url: `/key/${kid}?csrf_token=${csrf}`,
        method: 'DELETE',
        dataType: 'json',
    }).done((result) => {
        if (result.error) {
            $('#keys .error').text(result.error);
        } else {
            $row.remove();
        }
        if (result.csrf) {
            $('#keys').data('csrf', result.csrf);
        }
    }).fail((jqXhr, status) => {
        $('#keys .error').text(status);
    });
}

function addStream(ev) {
    const $row = $(ev.target).parents('tr');
    const data = {
        title: $row.find('input[name="title"]').val(),
        directory: $row.find('input[name="directory"]').val(),
        marlin_la_url: $row.find('input[name="marlin_la_url"]').val(),
        playready_la_url: $row.find('input[name="playready_la_url"]').val(),
        csrf_token: $('#streams').data('csrf'),
    };
    $row.find('.btn').attr("disabled", true);
    $('#streams .error').text('');
    $.ajax({
        url: '/stream',
        method: 'PUT',
        contentType: "application/json; charset=utf-8",
        data: JSON.stringify(data),
        dataType: 'json',
    }).done((result) => {
        if (result.error) {
            $('#streams .error').text(result.error);
            return;
        }
        if (result.csrf) {
            $('#streams').data('csrf', result.csrf);
        }
        reloadContent();
    });
}

function deleteStream(ev) {
    function onClick(btnEv) {
        btnEv.preventDefault();
        closeDialog();
        const cmd = $(btnEv.target).data("cmd");
        if (cmd === "yes") {
            confirmDeleteStream(id, csrf);
        }
        return false;
    }

    ev.preventDefault();

    const id = $(ev.target).data("id");
    if (!id) {
        return false;
    }
    let csrf = $('#streams').data('csrf');
    if (!csrf) {
        const input = $('#edit-model input[name="csrf_token"]');
        if (!input) {
            return false;
        }
        csrf = input[0].value;
    }
    const title = $(ev.target).data('title');
    const directory = $(ev.target).data('directory');
    const dialog = $('#dialog-box');
    dialog.find(".modal-body").html(
        `<div><h3>Delete stream &quot;${ title }&quot; ?</h3>
        <p>This will also delete all of the media files for this stream</p></div>`);
    dialog.find(".modal-footer").html(
      `<div>
      <button class="btn btn-danger" style="margin:1em" data-cmd="yes">
      Delete stream ${directory }</button>
      <button class="btn btn-secondary" data-cmd="no">Cancel</button>
      </div>`);
    dialog.find(".modal-footer .btn").one('click', onClick);
    showDialog();
    return false;
}

function confirmDeleteStream(id, csrf) {
    if (!id) {
        return;
    }
    $('#streams .error').text('');
    $.ajax({
        accepts: 'application/json',
        url: `/stream/${id}`,
        method: 'DELETE',
        dataType: 'json',
        data: {
            csrf_token: csrf,
            ajax: 1,
        },
    }).done((result) => {
        if (result.error) {
            $('#streams .error').text(result.error);
        } else {
            window.location = $('#media-management').data('back');
        }
    }).fail((jqXhr, status) => {
        $('#streams .error').text(status);
    });
}

function indexFile(ev) {
    const $row = $(ev.target).parents('tr');
    const $btn = $(ev.target);
    const blobId = $btn.data('key');
    const filename = $row.find('.filename').text();
    if (!blobId) {
        return;
    }
    const csrf = $('#media-files').data('csrf');
    const dialog = $('#dialog-box');
    dialog.find(".modal-body").html(`<p>Indexing ${ filename }</p>`);
    showDialog();
    $.ajax({
        url: `/media/index/${ blobId }?csrf_token=${ csrf }`,
        method: 'GET',
        dataType: 'json',
    }).done((result) => {
        if (result.csrf) {
            $('#media-files').data('csrf', result.csrf);
        }
        if (result.errors && result.errors.length) {
            const errs = result.errors.map(err => `<p>${ err }</p>`);
            dialog.find('.modal-body').html(`<div class="error">${ errs }</div>`);
            return;
        }
        dialog.find(".modal-body").html(`<p>Indexing ${filename} complete</p>`);
        if (result.representation) {
            $row.find('td.codec').text(result.representation.codecs);
            if (result.representation.encrypted) {
                $row.find('td.encrypted').html('<span class="bool-yes ">&check;</span>');
                $row.find('td.kid').html("");
                for (let i = 0; i < result.representation.kids.length; ++i) {
                    $row.find('td.kid').append(
                        `<p>${ encodeURIComponent(result.representation.kids[i]) }</p>`);
                }
            } else {
                $row.find('td.encrypted').html('<span class="bool-no ">&cross;</span>');
            }
            $row.find('.btn-index').addClass('btn-info').removeClass('btn-warning').text('Re-index');
            window.setTimeout(closeDialog, 750);
        }
    }).fail((e) => {
        const err = dialog.find('.modal-body .error');
        if (e.statusText) {
            err.text(`${ e.status } ${ e.statusText}`);
        } else if (e.responseText) {
            err.text(e.responseText);
        } else {
            err.text(JSON.stringify(e));
        }
    });
}

function deleteFile(ev) {
    const $btn = $(ev.target);
    ev.preventDefault();
    const href = $btn.attr('href');
    const csrf = $('#media-files').data('csrf');
    $('#media .error').text('');
    $.ajax({
        url: `${href}?csrf_token=${csrf}`,
        method: 'DELETE',
        dataType: 'json',
    }).done((result) => {
        if (result.error) {
            $('#media .error').text(result.error);
        }
        if (result.csrf) {
            $('#media-files').data('csrf', result.csrf);
        }
	reloadContent();
    }).fail((jqXhr, status) => {
        $('#media .error').text(status);
    });
}

function uploadFile(ev) {
    ev.preventDefault();
    const form = $("#upload-form");
    const filename = form.find('input[name="file"]').val();
    if (filename === "") {
        window.alert("No file selected");
        return;
    }
    form.find('input[name="ajax"]').val("1");
    const data = new FormData(form[0]);
    $("#upload-form .submit").prop("disabled", true);
    const dialog = $('#dialog-box');
    dialog.find(".modal-body").html(
        `<p>Uploading ${encodeURIComponent(filename)}</p><div class="error"></div>`);
    showDialog();
    $.ajax({
        url: form.attr("action"),
        data,
        type: "POST",
        enctype: 'multipart/form-data',
        processData: false,
        contentType: false,
        timeout: 600000,
        cache: false,
    }).done((data) => {
        $("#btnSubmit").prop("disabled", false);
        if (data.error) {
            const err = dialog.find('.modal-body .error');
            err.text(data.error);
            return;
        }
        dialog.find(".modal-body").html(
            `<p>Finished uploading ${filename}<span class="bool-yes ">&check;</span>`);
        if (data.upload_url) {
            $('#upload-form').attr('action', data.upload_url);
        }
        if (data.csrf_token) {
            $('#upload-form input[name="csrf_token"]').val(data.csrf_token);
        }
	closeDialog();
        reloadContent();
    }).fail((e) => {
        const err = dialog.find('.modal-body .error');
        if (e.responseJSON) {
            err.text(e.responseJSON.error);
        }
        else if (e.statusText) {
            err.text(`${e.status} ${e.statusText}`);
        } else if (e.responseText) {
            err.text(e.responseText);
        } else {
            err.text(JSON.stringify(e));
        }
	closeDialog();
    });
    return false;
}

function showDialog() {
    const dialog = $('#dialog-box');
    dialog.addClass("dialog-active show");
    dialog.css({ display: "block", });
    $('.modal-backdrop').addClass('show');
    $('.modal-backdrop').removeClass('hidden');
    $('body').addClass('modal-open');
}

function closeDialog() {
    const dialog = $('#dialog-box');
    dialog.removeClass("dialog-active").removeClass("show");
    dialog.css("display", "");
    $(document.body).removeClass("modal-open");
    $(document.body).css('overflow', '');
    $('.modal-backdrop').addClass('hidden');
    $('.modal-backdrop').removeClass("show");
}

addClickListeners();
enableTooltips();
