import $ from '/libs/jquery.js';

const allDrms = ['clearkey', 'marlin', 'playready',];

function updateEventFields() {
    const { selectedOptions } = document.getElementById('model-events');
    $('.prefix-ping, .prefix-scte35').addClass('not-selected');
    for (let i=0; i < selectedOptions.length; ++i) {
        const { value } = selectedOptions[i];
        $(`.prefix-${value}`).removeClass('not-selected');
    }
}

function updateDrmFields() {
    allDrms.forEach((name) => {
        if (document.getElementById(`model-drm_${name}`)?.checked) {
            $(`.${name}-option`).removeClass('not-selected');
            $(`.prefix-${name}`).removeClass('not-selected');
        } else {
            $(`.prefix-${name}`).addClass('not-selected');
        }
    });
}

updateEventFields();
$('#model-events').on('change', updateEventFields);
updateDrmFields();
$('.drm-checkbox').on('change', updateDrmFields);
