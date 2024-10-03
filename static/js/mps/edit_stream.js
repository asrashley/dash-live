import { setupValidation, serializeForm } from '../form_validation.js';

function addAlert(message, status) {
  const form = document.getElementById('edit_mps_form');
  const div = document.createElement('div');
  div.className = `alert alert-${ status } alert-dismissible fade show`;
  div.setAttribute('role', 'alert');
  div.innerHTML = `<span>${ message }</span>` +
    '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>';
  form.before(div);
}

async function handleFormSubmit(ev, form) {
  const exclude = new Set([
    'new_period_duration', 'new_period_start', 'new_period_stream']);
  ev.preventDefault();
  const data = serializeForm(form, exclude);
  console.dir(data);
  const url = form.getAttribute('action');
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
    addAlert(
      `Failed to save changes - ${ fetchResult.status }: ${ fetchResult.statusText }`,
      'danger');
    return false;
  }
  const {success, errors, next } = await fetchResult.json();
  if (success === true && next) {
    window.location = next;
  } else {
    for (const [name, value] of Object.entries(errors)) {
      addAlert(`${ name }: ${ value}`, 'warning');
    }
  }
  return false;
}

function handleAddPeriod(ev) {
  ev.preventDefault();
  const form = document.getElementById('edit_mps_form');
  const data = serializeForm(form);
  const period_ids = new Set();
  for (const [name, value] of Object.entries(data)) {
    if (name.endsWith('_pid')) {
      period_ids.add(value);
    }
  }
  const tbody = document.querySelector('.period-table tbody');
  const newPeriodId = parseInt(form['num_new_periods'].value, 10);
  form['num_new_periods'].value = `${newPeriodId + 1}`;
  let index = 1;
  let new_pid = `p${ newPeriodId + index}`;
  while (period_ids.has(new_pid)) {
    index++;
    new_pid = `p${ newPeriodId + index}`;
  }
  const { length } = tbody.querySelectorAll('tr');
  const placeholder = document.querySelector('.period-table .placeholder-row');
  const row = document.createElement('tr');
  const fieldNames = `new_period_${ newPeriodId }_`
  row.innerHTML = placeholder.innerHTML.replaceAll('new_period_', fieldNames);
  row.classList.remove('hidden');
  row.querySelector('.period-ordering input').value = length;
  row.querySelector('.period-id input').value = new_pid;
  tbody.appendChild(row);
  return false;
}

function setupFormHandlers() {
    const { form, signal } = setupValidation('edit_mps_form', {
        cleanupOnSubmit: false,
    });
    form.addEventListener('submit', (ev) => handleFormSubmit(ev, form));

    const btn = document.getElementById('add-period-btn');
    btn.addEventListener('click', handleAddPeriod, { signal });
}

setupFormHandlers();

