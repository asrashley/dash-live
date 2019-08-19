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
            newRow.find('.btn-add').click(addKey);
            newRow.find('.btn-delete').click(deleteKey);
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

    function deleteMedia(ev) {
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
    
    $('#keys .btn-add').click(addKey);
    $('#keys .btn-delete').click(deleteKey);
    $('#media-files .btn-delete').click(deleteMedia);
});
