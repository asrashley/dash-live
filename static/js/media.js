$(document).ready(function () {
    'use strict';
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
            url: document.location + '?fragment=1',
            method: 'GET',
        }).done(function (result) {
            removeClickListeners();
            $('#media-management').parent().html(result);
            addClickListeners();
        });
    }
    function addKey(ev) {
        var kid, key, csrf;
        var $row = $(ev.target).parents('tr');
        kid = $row.find('input[name="kid"]').val();
        key = $row.find('input[name="key"]').val();
        csrf = $('#keys').data('csrf');
        $row.find('.btn').attr("disabled", true);
        $('#keys .error').text('');
        $.ajax({
            url: '/key',
            method: 'PUT',
            data: {
                "kid": kid,
                "key": key,
                "csrf_token": csrf
            },
            dataType: 'json',
        }).done(function (result) {
            var newRow;
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
        var kid, key, csrf;
        var $row = $(ev.target).parents('tr');
        kid = $row.find('.kid').text();
        csrf = $('#keys').data('csrf');
        if (!kid) {
            return;
        }
        $('#keys .error').text('');
        $.ajax({
            url: '/key/' + kid + "?csrf_token=" + csrf,
            method: 'DELETE',
            dataType: 'json',
        }).done(function (result) {
            if (result.error) {
                $('#keys .error').text(result.error);
            } else {
                $row.remove();
            }
            if (result.csrf) {
                $('#keys').data('csrf', result.csrf);
            }
        }).fail(function (jqXhr, status) {
            $('#keys .error').text(status);
        });
    }

    function addStream(ev) {
        var data;
        var $row = $(ev.target).parents('tr');
        data = {
            'title': $row.find('input[name="title"]').val(),
            'directory': $row.find('input[name="directory"]').val(),
            'marlin_la_url': $row.find('input[name="marlin_la_url"]').val(),
            'playready_la_url': $row.find('input[name="playready_la_url"]').val(),
            'csrf_token': $('#streams').data('csrf')
        };
        $row.find('.btn').attr("disabled", true);
        $('#streams .error').text('');
        $.ajax({
            url: '/stream',
            method: 'PUT',
            contentType: "application/json; charset=utf-8",
            data: JSON.stringify(data),
            dataType: 'json'
        }).done(function (result) {
            var newRow;
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
        var dialog, id, title, $row, csrf, input;

        function onClick(btnEv) {
            var cmd;

            btnEv.preventDefault();
            closeDialog();
            cmd = $(btnEv.target).data("cmd");
            if (cmd === "yes") {
                confirmDeleteStream($row, id, csrf);
            }
            return false;
        }

        ev.preventDefault();

        id = $(ev.target).data("id");
        if (!id) {
            return false;
        }
        csrf = $('#streams').data('csrf');
        if (!csrf) {
            input = $('#edit-model input[name="csrf_token"]');
            if (!input) {
                return false;
            }
            csrf = input[0].value;
        }
        $row = $(ev.target).parents('tr');
        if ($row.length) {
            title = $row.find('.title').text();
            if (title === "" || title === undefined) {
                title = $row.find('.directory').text();
            }
        } else {
            title = ev.target.innerText.slice(7, -1);
        }
        dialog = $('#dialog-box');
        dialog.find(".modal-body").html(
            '<div><h3>Delete stream &quot;' + title + '&quot; ?</h3>' +
                '<p>This will also delete all of the media files for this stream</p></div>');
        dialog.find(".modal-footer").html(
            '<div>' +
            '<button class="btn btn-danger" style="margin:1em" data-cmd="yes">Delete Stream</button>' +
            '<button class="btn btn-secondary" data-cmd="no">Cancel</button>' +
            '</div>');
        dialog.find(".modal-footer .btn").one('click', onClick);
        showDialog();
        return false;
    }

    function confirmDeleteStream($row, id, csrf) {
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
        }).done(function (result) {
            if (result.error) {
                $('#streams .error').text(result.error);
            } else {
                window.location = $('#media-management').data('back');
            }
        }).fail(function (jqXhr, status) {
            $('#streams .error').text(status);
        });
    }

    function indexFile(ev) {
        var dialog, blobId, filename, csrf;
        var $row = $(ev.target).parents('tr');
        var $btn = $(ev.target);
        blobId = $btn.data('key');
        filename = $row.find('.filename').text()
        if (!blobId) {
            return;
        }
        csrf = $('#media-files').data('csrf');
        dialog = $('#dialog-box');
        dialog.find(".modal-body").html('<p>Indexing ' + filename +
            '</p><div class="error"></div>');
        showDialog();
        $.ajax({
            url: '/media/index/' + blobId + '?csrf_token=' + csrf,
            method: 'GET',
            dataType: 'json',
        }).done(function (result) {
            var i;
            if (result.error) {
                dialog.find('.modal-body .error').text(result.error);
            } else {
                dialog.find(".modal-body").html('<p>Indexing ' +
                    filename + ' complete</p>');
                if (result.representation) {
                    $row.find('td.codec').text(result.representation.codecs);
                    if (result.representation.encrypted) {
                        $row.find('td.encrypted').html('<span class="bool-yes ">&check;</span>');
                        $row.find('td.kid').html("");
                        for (i = 0; i < result.representation.kids.length; ++i) {
                            $row.find('td.kid').append(
                                '<p>' +
                                encodeURIComponent(result.representation.kids[i]) +
                                '</p>');
                        }
                    } else {
                        $row.find('td.encrypted').html('<span class="bool-no ">&cross;</span>');
                    }
                    $row.find('.btn-index').addClass('btn-info').removeClass('btn-warning').text('Re-index');
                    window.setTimeout(closeDialog, 750);
                }
            }
            if (result.csrf) {
                $('#media-files').data('csrf', result.csrf);
            }
        }).fail(function (e) {
            var err = dialog.find('.modal-body .error');
            if (e.statusText) {
                err.text(e.status + ' ' + e.statusText);
            } else if (e.responseText) {
                err.text(e.responseText);
            } else {
                err.text(JSON.stringify(e));
            }
        });
    }

    function deleteFile(ev) {
        var href, csrf;
        var $row = $(ev.target).parents('tr');
        var $btn = $(ev.target);
	ev.preventDefault();
        href = $btn.attr('href');
        csrf = $('#media-files').data('csrf');
        $('#media .error').text('');
        $.ajax({
            url: href + '?csrf_token=' + csrf,
            method: 'DELETE',
            dataType: 'json',
        }).done(function (result) {
            if (result.error) {
                $('#media .error').text(result.error);
            }
            if (result.csrf) {
                $('#media-files').data('csrf', result.csrf);
            }
	    reloadContent();
        }).fail(function (jqXhr, status) {
            $('#media .error').text(status);
        });
    }
    function uploadFile(ev) {
        var form, data, dialog, filename;
        ev.preventDefault();
        form = $("#upload-form");
        filename = form.find('input[name="file"]').val();
        if (filename === "") {
            alert("No file selected");
            return;
        }
        form.find('input[name="ajax"]').val("1");
        data = new FormData(form[0]);
        $("#upload-form .submit").prop("disabled", true);
        dialog = $('#dialog-box');
        dialog.find(".modal-body").html('<p>Uploading ' +
            encodeURIComponent(filename) +
            '</p><div class="error"></div>');
        showDialog();
        $.ajax({
            url: form.attr("action"),
            data: data,
            type: "POST",
            enctype: 'multipart/form-data',
            processData: false,
            contentType: false,
            timeout: 600000,
            cache: false
        }).done(function (data) {
            var err, htm;

            $("#btnSubmit").prop("disabled", false);
            if (data.error) {
                err = dialog.find('.modal-body .error');
                err.text(data.error);
                return;
            }
            dialog.find(".modal-body").html('<p>Finished uploading ' +
                filename +
                '<span class="bool-yes ">&check;</span>');
            if (data.upload_url) {
                $('#upload-form').attr('action', data.upload_url);
            }
            if (data.csrf_token) {
                $('#upload-form input[name="csrf_token"]').val(data.csrf_token);
            }
	    closeDialog();
            reloadContent();
        }).fail(function (e) {
            var err = dialog.find('.modal-body .error');
            if (e.responseJSON) {
                err.text(e.responseJSON.error);
            }
            else if (e.statusText) {
                err.text(e.status + ' ' + e.statusText);
            } else if (e.responseText) {
                err.text(e.responseText);
            } else {
                err.text(JSON.stringify(e));
            }
            console.error(e);
	    closeDialog();
        });
        return false;
    }

    function showDialog() {
        var dialog = $('#dialog-box');
        dialog.addClass("dialog-active show");
        dialog.css({ display: "block" });
        $('.modal-backdrop').addClass('show');
        $('.modal-backdrop').removeClass('hidden');
        $('body').addClass('modal-open');
    }

    function closeDialog() {
        var dialog = $('#dialog-box');
        dialog.removeClass("dialog-active").removeClass("show");
        dialog.css("display", "");
        $(document.body).removeClass("modal-open");
        $('.modal-backdrop').addClass('hidden');
        $('.modal-backdrop').removeClass("show");
    }

    addClickListeners();
});
