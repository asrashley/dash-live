import { html } from 'htm/preact';
import { useCallback, useContext, useEffect, useMemo, useState } from 'preact/hooks';
import { useComputed } from "@preact/signals";

import { Alert } from '../../components/Alert.js';
import { TextInput } from '../../components/TextInput.js';
import { AppStateContext, createAppState } from '../../appState.js';
import { TimeDeltaInput } from '../../components/TimeDeltaInput.js';
import { PageStateContext, modifyModel, validatePeriod } from '../state.js';

function StreamSelect({value, onChange, name}) {
  const { allStreams } = useContext(PageStateContext);
  const streams = allStreams.value ?? [];

  const changeHandler = useCallback((ev) => {
    onChange({
      name,
      value: parseInt(ev.target.value, 10),
    });
  }, [onChange, name]);

  return html`
<select class="form-select" value=${ value } name=${name}
  onChange=${changeHandler} >
  <option value="">--Select a stream--</option>
  ${ streams.map(s => html`<option value=${s.pk}>${s.title}</option>`) }
</select>`;
}

function PeriodRow({className="", period}) {
  const { pid, pk, ordering, stream, start, duration, tracks } = period;
  const { model, allStreams, streamsMap, modified } = useContext(PageStateContext);
  const { dialog }  = useContext(AppStateContext);
  const numTracks = useMemo(() => {
    const count = Object.keys(tracks).length;
    if (count === 0) {
      return 'choose';
    }
    if (count === 1) {
      return '1 track';
    }
    return `${count} tracks`;
  }, [tracks]);
  const errors = useMemo(() => validatePeriod(period), [period]);

  const selectTracks = useCallback(() => {
    dialog.value = {
      backdrop: true,
      trackPicker: {
        pk,
        pid,
        stream: streamsMap.value.get(stream),
      },
    };
  }, [dialog, stream, streamsMap.value]);

  const setPid = useCallback((ev) => {
    model.value = modifyModel({
      model: model.value,
      periodPk: pk,
      period: {
        'pid': ev.target.value,
      }
    });
    modified.value = true; 
  }, [pk, model.value, modified]);

  const setField = useCallback(({name, value}) => {
    const fieldName = name.split('_')[0];
    model.value = modifyModel({
      model: model.value,
      periodPk: pk,
      period: {
        [fieldName]: value,
      }
    });
    modified.value = true; 
  }, [model, modified]);

  return html`
    <tr class="${ className }" data-pk=${pk}>
      <td class="period-ordering">${ ordering }</td>
      <td class="period-id">
        <${TextInput} value=${pid} name="pid_${pk}" onInput=${setPid} 
          error=${errors.pid} required />
      </td>
      <td class="period-stream">
        <${StreamSelect} name="stream_${pk}" value=${stream}
          onChange=${setField} error=${errors.stream} />
      </td>
      <td class="period-start">
        <${TimeDeltaInput} value=${start} name="start_${pk}"
          onChange=${setField} error=${errors.start} />
      </td>
      <td class="period-duration">
        <${TimeDeltaInput} value=${duration} name="duration_${pk}"
          onChange=${setField} min="00:00:01" error=${errors.duration} />
      </td>
      <td class="period-tracks">
          <a class="btn btn-sm m-1 btn-secondary" onClick=${selectTracks}>
            ${ numTracks }</a>
      </td>
    </tr>`;
}

export function PeriodsTable({errors}) {
  const { model, allStreams, streamsMap } = useContext(PageStateContext);
  const periods = useComputed(() => model.value?.periods ?? []);
  const errorsDiv = useComputed(() => {
    if (errors.value.periods === undefined) {
      return null;
    }
    return html`<${Alert} text=${errors.value.periods} level="warning" />`;
  });

  return html`
    <table class="table table-striped period-table">
      <thead>
        <tr>
          <th class="period-ordering">#</th>
          <th class="period-id">ID</th>
          <th class="period-stream">Stream</th>
          <th class="period-start">Start Time</th>
          <th class="period-duration">Duration</th>
          <th class="period-tracks">Tracks</th>
        </tr>
      </thead>
      <tbody>
        ${ periods.value.map(prd => html`
    <${PeriodRow} key=${prd.pk} errors=${errors} period=${prd} />`) }
      </tbody>
    </table>${ errorsDiv.value }`;
}
