$(document).ready(function () {
    'use strict';
    const allDrms = ['clearkey', 'marlin', 'playready'];
    function updateEventFields() {
        const { selectedOptions } = document.getElementById('model-events');
        $('.prefix-ping, .prefix-scte35').addClass('hidden');
        for (let i=0; i < selectedOptions.length; ++i) {
            const { value } = selectedOptions[i];
            $(`.prefix-${value}`).removeClass('hidden');
        }
    }
    function updateDrmFields() {
        /* $('.drm-location').addClass('hidden');*/
        allDrms.forEach((name) => {
            if (document.getElementById(`model-drm_${name}`)?.checked) {
                $(`.${name}-option`).removeClass('hidden');
                $(`.prefix-${name}`).removeClass('hidden');
            } else {
                $(`.prefix-${name}`).addClass('hidden');
            }
        });
        /*if (document.getElementById('model-drm_clearkey')?.checked) {
            $('.row-field-clearkey_drmloc').removeClass('hidden');
        }*/
    }
    updateEventFields();
    updateDrmFields();
    $('#model-events').on('change', updateEventFields);
    $('.drm-checkbox').on('change', updateDrmFields);
});
