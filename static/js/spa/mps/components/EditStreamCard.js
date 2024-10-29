import { html } from 'htm/preact';
import { useCallback, useContext } from 'preact/hooks';
import { useSignal, useComputed } from "@preact/signals";
import { Link } from "wouter-preact";
import { navigate } from "wouter/use-browser-location";

import { Card, TextInput } from '@dashlive/ui';
import { PeriodsTable } from './PeriodsTable.js';
import { AppStateContext, appendMessage } from '../../appState.js';
import { PageStateContext, validateModel } from '../state.js';
import { EndpointContext } from '../../endpoints.js';
import { routeMap } from '/libs/routemap.js';

function FormRow({className="", name, label, text, children, error}) {
  const textDiv = text ? html`<div class="col-3 form-text">${ text }</div>` : null;
  const errDiv = error ? html`<div class="invalid-feedback">${error}</div>` : null;

  return html`
<div class="row mb-3 form-group ${className}">
  <label class="col-2 col-form-label" htmlFor="field-${name}">${ label }:</label>
  <div class="${text ? 'col-7' : 'col-10'}">${ children }</div>
${ textDiv }${ errDiv }
</div>
`;
}

function TextInputRow({name, label, text, error, value, onInput}) {
  return html`
<${FormRow} name=${name} label=${label} text=${text} error=${error} >
  <${TextInput} name="${name}" value=${value} onInput=${onInput} required />
</${FormRow}>`;
}

function EditStreamForm({name}) {
  const apiRequests = useContext(EndpointContext);
  const { model, modified } = useContext(PageStateContext);
  const { messages } = useContext(AppStateContext);
  const abortController = useSignal(new AbortController());
  const cancelUrl = routeMap.listMps.url();
  const saveChangesTitle = useComputed(() => {
    if (!model.value.pk) {
      return 'Add new stream';
    }
    return 'Save changes';
  });
  const errors = useComputed(() => validateModel(model.value));
  const disableSave = useComputed(() => {
    if (Object.keys(errors.value).length > 0) {
      console.log('has errors');
      return true;
    }
    console.log(`model.value.pk ${model.value.pk}`);
    if (model.value.pk === null) {
      return false;
    }
    return modified.value !== true;
  });

  const setName = useCallback((ev) => {
    model.value = {
      ...model.value,
      name: ev.target.value,
    };
  }, [model]);

  const setTitle = useCallback((ev) => {
    model.value = {
      ...model.value,
      title: ev.target.value,
    };
  }, [model]);

  const saveChanges = useCallback(async () => {
    const { signal } = abortController.value;
    if (!model.value || signal.aborted) {
      return;
    }
    const periods = model.value.periods.map(prd => {
      const period = {
        ...prd,
        pk: typeof(prd.pk) === "number" ? prd.pk : null,
      };
      return period;
    });
    const data = {
      ...model.value,
      spa: true,
      periods,
    };
    try {
      const result = data.pk === null ?
            await apiRequests.addMultiPeriodStream(data, {signal}) :
            await apiRequests.modifyMultiPeriodStream(name, data, {signal});
      if (signal.aborted) {
        return;
      }
      result.errors?.forEach(
        (err) => appendMessage(messages, err, 'warning'));
      if (result?.success === true) {
        if (data.pk === null) {
          appendMessage(messages, `Successfully added new stream ${name}`,
                        'success');
        } else {
          appendMessage(messages, `Successfully saved changes to ${name}`,
                        'success');
        }
        modified.value = false;
        model.value = result.model;
        if (data.pk === null) {
          const href = routeMap.listMps.url();
          navigate(href, {replace: true});
        }
      }
    } catch(err) {
      appendMessage(messages, `${err}`, 'warning');
    }
  }, [abortController.value, apiRequests, messages, model, modified, name]);

  if (!model.value) {
    return html`<h3>Fetching data for stream "${ name }"...</h3>`;
  }

  return html`<div class="was-validated">
  <${TextInputRow} name="name" label="Name" value=${model.value.name}
     text="Unique name for this stream" onInput=${setName}
     error=${errors.value.name} />
  <${TextInputRow} name="title" label="Title" value=${model.value.title}
    text="Title for this stream" onInput=${setTitle}
    error=${errors.value.title} />
  <${FormRow} className="has-validation" name="periods" label="Periods">
    <${PeriodsTable} errors=${errors} />
  </${FormRow}>
  <div class="btn-toolbar">
    <button class="btn btn-success btn-sm m-2" disabled=${disableSave.value}
      onClick=${saveChanges} >${ saveChangesTitle }</button>
    <${Link} class="btn btn-danger btn-sm m-2" to=${ cancelUrl }>Cancel</${Link}>
  </div>
</div>`;
}

export function EditStreamCard({name, newStream}) {
  const { allStreams, model } = useContext(PageStateContext);
  const header = newStream ?
        html`<h2>Add new Multi-Period stream</h2>` :
        html`<h2>Editing Multi-Period stream "${ name }"</h2>`;
  return html`
<${Card} header=${header} id="edit_mps_form">
  <${EditStreamForm} model=${model} name=${name} allStreams=${allStreams} />
</${Card}>`;
}
