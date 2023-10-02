$(document).ready(function () {
    'use strict';
    function updateEventFields() {
        const { selectedOptions } = document.getElementById('model-events');
        $('.prefix-ping, .prefix-scte35').addClass('hidden');
        for (let i=0; i < selectedOptions.length; ++i) {
            const { value } = selectedOptions[i];
            $(`.prefix-${value}`).removeClass('hidden');
        }
    }
    updateEventFields();
    $('#model-events').on('change', updateEventFields);    
});
