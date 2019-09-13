$(document).ready(function(){
    'use strict';
    function addKey(ev) {
        var kid, key;
        var $row = $(ev.target).parents('tr');
        kid = $row.find('input[name="kid"]').val();
        key = $row.find('input[name="key"]').val();
        console.log('add key',kid,key);
        $row.find('.btn').attr("disabled", true);
        $('#keys .error').text('');
        $.ajax({
            url: '/key',
            method: 'PUT',
            data: { "kid":kid, "key": key },
            dataType: 'json',
        }).done(function(result) {
            var newRow;
            if(result.error) {
                $('#keys .error').text(result.error);
                return;
            }
            newRow = $('#keys .placeholder').clone();
            newRow.removeClass('placeholder');
            newRow.find('.kid').text(result.kid);
            newRow.find('.key').text(result.key);
            if (result.computed===true) {
                newRow.find('.computed').html('<span class="bool-yes">&check;</span>');
            } else {
                newRow.find('.computed').html('<span class="bool-no">&cross;</span>');
            }
            $('#keys tbody').append(newRow);
            newRow.find('.add-key').click(addKey);
            newRow.find('.delete-key').click(deleteKey);
            newRow.find('.btn-index').click(indexFile);
            $row.find('input[name="kid"]').val('');
            $row.find('input[name="key"]').val('');
        }).always(function() {
            $row.find('.btn').removeAttr("disabled");
        });
    }
    
    function deleteKey(ev) {
        var kid, key;
        var $row = $(ev.target).parents('tr');
        kid = $row.find('.kid').text();
        console.log('delete key',kid);
        if (!kid) {
            return;
        }
        $('#keys .error').text('');
        $.ajax({
            url: '/key/'+kid,
            method: 'DELETE',
            dataType: 'json',
        }).done(function(result) {
            if(result.error) {
                $('#keys .error').text(result.error);
            } else {
                $row.remove();
            }
        }).fail(function(jqXhr, status) {
            $('#keys .error').text(status);
        });
    }

    function addStream(ev) {
        var title, prefix;
        var $row = $(ev.target).parents('tr');
        title = $row.find('input[name="title"]').val();
        prefix = $row.find('input[name="prefix"]').val();
        console.log('add stream',title,prefix)
        $row.find('.btn').attr("disabled", true);
        $('#streams .error').text('');
        $.ajax({
            url: '/stream',
            method: 'PUT',
            data: { "title":title, "prefix": prefix },
            dataType: 'json',
        }).done(function(result) {
            var newRow;
            if(result.error) {
                $('#streams .error').text(result.error);
                return;
            }
            newRow = $('#streams .placeholder').clone();
            newRow.removeClass('placeholder');
            newRow.find('.title').text(result.title);
            newRow.find('.prefix').text(result.prefix);
            newRow.find('.delete-stream').data("id", result.id);
            $('#streams tbody').append(newRow);
            newRow.find('.delete-stream').click(deleteStream);
            $row.find('input[name="title"]').val('');
            $row.find('input[name="prefix"]').val('');
        }).always(function() {
            $row.find('.btn').removeAttr("disabled");
        });
    }
    
    function deleteStream(ev) {
        var id;
        var $row = $(ev.target).parents('tr');
        id = $(ev.target).data("id");
        console.log('delete stream',id);
        if (!id) {
            return;
        }
        $('#streams .error').text('');
        $.ajax({
            url: '/stream/'+id,
            method: 'DELETE',
            dataType: 'json',
        }).done(function(result) {
            if(result.error) {
                $('#streams .error').text(result.error);
            } else {
                $row.remove();
            }
        }).fail(function(jqXhr, status) {
            $('#streams .error').text(status);
        });
    }

    function indexFile(ev) {
        var $row = $(ev.target).parents('tr');
        var $btn = $(ev.target);
        var dialog, blobId, filename;
        blobId = $btn.data('key');
        filename = $row.find('.filename').text()
        if (!blobId) {
            return;
        }
        console.log('index blob',blobId);
        dialog = $('#dialog-box')
        dialog.find(".modal-body").html('<p>Indexing ' + filename + '</p><div class="error"></div>');
        showDialog();
        $.ajax({
            url: '/media/'+blobId+'?index=1',
            method: 'GET',
            dataType: 'json',
        }).done(function(result) {
            if(result.error) {
              var i;
              dialog.find('.modal-body .error').text(result.error);
            } else {
                dialog.find(".modal-body").html('<p>Indexing ' + filename + ' complete</p>');
                if (result.representation) {
                    $row.find('td.codec').text(result.representation.codecs);
                    if(result.representation.encrypted) {
                        $row.find('td.encrypted').html('<span class="bool-yes ">&check;</span>');
                        $row.find('td.kid').html("");
                        for(i=0; i < result.representation.kids.length; ++i) {
                          $row.find('td.kid').append('<p>'+result.representation.kids[i]+'</p>');
                        }
                    } else {
                        $row.find('td.encrypted').html('<span class="bool-no ">&cross;</span>');
                    }
                    $row.find('.btn-index').addClass('btn-info').removeClass('btn-warning').text('Re-index');
                    window.setTimeout(closeDialog, 500);
                }
            }
        }).fail(function(jqXhr, status) {
            dialog.find('.modal-body .error').text(result.error);
        });
    }

    function showDialog() {
        var dialog = $('#dialog-box');
        dialog.addClass("dialog-active show");
        dialog.css({display: "block"});
        $('.modal-backdrop').addClass('show');
        $('.modal-backdrop').removeClass('hidden');
        $('body').addClass('modal-open');
    }

    function closeDialog() {
        var dialog;
        
        dialog = $('#dialog-box')
        dialog.removeClass("dialog-active").removeClass("show");
        dialog.css("display", "");
        $(document.body).removeClass("modal-open");
        $('.modal-backdrop').addClass('hidden');
        $('.modal-backdrop').removeClass("show");
    }

    function deleteFile(ev) {
        var blobId;
        var $row = $(ev.target).parents('tr');
        var $btn = $(ev.target);
        blobId = $btn.data('key');
        if (!blobId) {
            return;
        }
        console.log('delete blob',blobId);
        $('#media .error').text('');
        $.ajax({
            url: '/media/'+blobId,
            method: 'DELETE',
            dataType: 'json',
        }).done(function(result) {
            if(result.error) {
                $('#media .error').text(result.error);
            } else {
                $row.remove();
            }
        }).fail(function(jqXhr, status) {
            $('#media .error').text(status);
        });
    }
    function uploadFile(ev) {
        var form, data, dialog, filename;
        ev.preventDefault();
        form = $("#upload-form");
        filename = form.find('input[name="file"]').val();
        console.log("Filename: "+filename);
        if (filename === "") {
            alert("No file selected");
            return;
        }
        form.find('input[name="ajax"]').val("1");
        data = new FormData(form[0]);
        $("#upload-form .submit").prop("disabled", true);
        dialog = $('#dialog-box')
        dialog.find(".modal-body").html('<p>Uploading ' + filename + '</p><div class="error"></div>');
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
            console.dir(data);
            if(data.error) {
                err = dialog.find('.modal-body .error');
                err.text(data.error);
                return;
            }
            dialog.find(".modal-body").html('<p>Finished uploading ' + filename+ '<span class="bool-yes ">&check;</span>');
            if(data.form_html) {
                $('#upload-form').remove();
                htm = $(data.form_html);
                $('.form-container').append(htm);
                $("#upload-form .submit").click(uploadFile);
            }
            if(data.file_html){
                htm = $(data.file_html);
                htm.insertBefore('#media-files .error-row');
                htm = $('#'+data.name);
                htm.find('.delete-file').click(deleteFile);
                htm.find('.btn-index').click(indexFile);
                window.setTimeout(closeDialog, 500);
            }
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
        }).always(function() {
            $("#upload-form .submit").prop("disabled", false);
        });
        return false;
    }
     
    $('#keys .add-key').click(addKey); 
    $('#keys .delete-key').click(deleteKey);
    $('#streams .add-stream').click(addStream);
    $('#streams .delete-stream').click(deleteStream);
    $('#media-files .delete-file').click(deleteFile);
    $('#media-files .btn-index').click(indexFile);
    $("#upload-form .submit").click(uploadFile);
    $('#dialog-box .btn-close').click(closeDialog);
});
