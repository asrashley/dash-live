/**
 * Create an object with all the values from an HTML form
 * @param form {HTMLFormElement} the form to extract data from
 * @param exclude {Set} optional set of keys to exclude
 */
export function serializeForm(form, exclude) {
    const formData = new FormData(form);
    const data = {};
    for (const [key, value] of formData) {
        if (exclude === undefined || !exclude.has(key)) {
            data[key] = value;
        }
    }
    return data;
}

export async function validateFormValues(form_id) {
  const form = document.getElementById(form_id);
  if (form === null) {
    throw new Error('Failed to find form');
  }
  const url = form.getAttribute('data-validate-url');
  if (!url) {
    throw new Error('Failed to find URL for form validation');
  }
  const data = serializeForm(form);
  form.classList.add('needs-validation');
  form.classList.remove('was-validated');

  const fetchResult = await fetch(url, {
    body: JSON.stringify(data),
    cache: 'no-cache',
    credentials: 'same-origin',
    headers: {
      "Content-Type": "application/json",
    },
    method: 'POST',
    mode: 'same-origin',
  });
  if (!fetchResult.ok) {
    throw new Error(`Failed to check form validitity: ${ fetchResult.status }`);
  }
  const jsonResult = await fetchResult.json();
  const { csrf_token, errors = {} } = jsonResult ?? {};
  if (csrf_token) {
    form.csrf_token.value = csrf_token;
  }

  form.querySelectorAll('input').forEach((elt) => {
    if (elt.getAttribute('type') == 'hidden') {
      return;
    }
    const name = elt.getAttribute('name');
    const parent = elt.parentElement;
    if (name === null || parent === null) {
      return;
    }
    const feedback = parent.querySelector('.invalid-feedback');
    const err = errors[name] || '';
    if (err === '') {
      elt.classList.add('is-valid');
      elt.classList.remove('is-invalid');
    } else {
      elt.classList.remove('is-valid');
      elt.classList.add('is-invalid');
    }
    if (feedback !== null) {
      feedback.innerText = err;
    }
    elt.setCustomValidity(err);
  });
  form.classList.remove('needs-validation');
  form.classList.add('was-validated');
  return {
    form,
    ...jsonResult,
  };
}

export function setupValidation(form_id, options = {}) {
  const form = document.getElementById(form_id);
  const { cleanupOnSubmit = true } = options;

  if (form === null) {
    throw new Error(`Failed to find form "${ form_id }"`);
  }
  const controller = new AbortController();
  const { signal } = controller;

  const checkFormValues = () => {
    validateFormValues(form_id).catch(err => console.error(err));
  };

  for (let i = 0; i < form.elements.length; ++i) {
    const elt = form.elements[i];
    if (elt.nodeName === 'INPUT') {
      elt.addEventListener('change', checkFormValues, { signal, });
      elt.addEventListener('invalid', (ev) => {
        ev.target.classList.remove('is-valid');
        ev.target.classList.add('is-invalid');
      }, { signal, });
      elt.addEventListener('valid', (ev) => {
        ev.target.classList.add('is-valid');
        ev.target.classList.remove('is-invalid');
      }, { signal, });
    }
  }
  if (cleanupOnSubmit) {
    const submitHandler = () => {
      controller.abort();
      form.removeEventListener('submit', submitHandler);
    };
    form.addEventListener('submit', submitHandler);
  }
  return {form, controller, signal,};
}
