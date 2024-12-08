import $ from 'jquery';
import { enableTooltips } from './tooltips.js';
import { validateFormValues } from './form_validation.js';

async function checkFormValues() {
  try {
    const { form } = await validateFormValues('edit_media');
    const submit = $('#edit_media button[type="submit"]');
    if (form.checkValidity()) {
      submit.attr('disabled', false);
    } else {
      submit.attr('disabled', 'disabled');
    }
  } catch(err) {
    console.error(err);
    return;
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
