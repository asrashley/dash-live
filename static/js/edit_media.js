/* globals console */
import $ from '/libs/jquery.js';
import { enableTooltips } from './tooltips.js';

async function checkFormValues() {
    const form = document.getElementById('edit_media');
    if (form === null) {
        console.error('Failed to find edit media form');
        return;
    }
    const url = $(form).data('validate-url');
    if (!url) {
        console.error('Failed to find URL for form validation');
        return;
    }
    const data = Object.fromEntries(
        $(form).serializeArray().
            filter(item => item.name !== 'csrf_token').
            map(item => [item.name, item.value,]));
    $('form').addClass('needs-validation').removeClass('was-validated');
    const result = await fetch(url, {
        body: JSON.stringify(data),
        cache: 'no-cache',
        credentials: 'same-origin',
        headers: {
            "Content-Type": "application/json",
        },
        method: 'POST',
        mode: 'same-origin',
    });
    if (!result.ok) {
        console.error(`Failed to check form validitity: ${ result.status }`);
        return;
    }
    const { errors } = await result.json();
    $('#edit_media input').each((_index, elt) => {
        const $elt = $(elt);
        const name = $elt.attr('name');
        const parent = $elt.parent();
        const feedback = parent.find('.invalid-feedback');
        const err = errors[name] || '';
        if (err === '') {
            $elt.addClass('is-valid').removeClass('is-invalid');
        } else {
            $elt.removeClass('is-valid').addClass('is-invalid');
        }
        feedback.text(err);
        elt.setCustomValidity(err);
    });
    $('form').removeClass('needs-validation').addClass('was-validated');
    const submit = $('#edit_media button[type="submit"]');
    if (form.checkValidity()) {
        submit.attr('disabled', false);
    } else {
        submit.attr('disabled', 'disabled');
    }
}

function setupValidation() {
    $('#edit_media input').on('change', checkFormValues);

    $('#edit_media input').on('invalid', (ev) => {
        $(ev.target).removeClass('is-valid').addClass('is-invalid');
    });

    $('#edit_media input').on('valid', (ev) => {
        $(ev.target).addClass('is-valid').removeClass('is-invalid');
    });
}

enableTooltips();
setupValidation();
