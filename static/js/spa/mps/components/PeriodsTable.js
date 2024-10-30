import { html } from 'htm/preact';
import { useCallback, useContext, useMemo } from 'preact/hooks';
import { useComputed } from '@preact/signals';

import {
  Alert,
  DropDownMenu,
  Icon,
  Sortable,
  TextInput,
  TimeDeltaInput
} from '@dashlive/ui';
import { AppStateContext } from '../../appState.js';
import {
  PageStateContext,
  addPeriod,
  removePeriod,
  modifyModel,
  setOrdering,
  validatePeriod
} from '../state.js';

function PeriodOrder({addPeriod, deletePeriod}) {
  const menu = [
    {
      title: 'Add another Period',
      onClick: addPeriod,
    },
    {
      title: 'Delete Period',
      onClick: deletePeriod,
    },
  ];

  return html`<${DropDownMenu} linkClass="" menu=${menu}>
  <${Icon} name="three-dots" />
  <//>`
}

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

const rowColours = ['bg-secondary-subtle', 'bg-primary-subtle'];

function PeriodRow({className="", index, item: period, addPeriod, ...props}) {
  const { pid, pk, stream, start, duration, tracks } = period;
  const { model, streamsMap, modified } = useContext(PageStateContext);
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
  }, [dialog, pid, pk, stream, streamsMap.value]);

  const setPid = useCallback((ev) => {
    model.value = modifyModel({
      model: model.value,
      periodPk: pk,
      period: {
        pid: ev.target.value,
      }
    });
    modified.value = true;
  }, [pk, model, modified]);

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
  }, [model, modified, pk]);

  const setStream = useCallback(({value}) => {
    const stream = streamsMap.value.get(value);

    model.value = modifyModel({
      model: model.value,
      periodPk: pk,
      period: {
        stream: value,
        duration: stream.duration,
      },
    });
    modified.value = true;
  }, [model, modified, pk, streamsMap.value])

  const deletePeriodBtn = useCallback(() => {
    model.value = removePeriod(model.value, pk);
  }, [model, pk]);

  const clsNames = `row mt-1 p-1 ${rowColours[index % rowColours.length]} ${className}`;

  return html`
    <li class="${clsNames}" ...${props}>
      <div class="col period-ordering">
        <${PeriodOrder} addPeriod=${addPeriod} deletePeriod=${deletePeriodBtn}/>
      </div>
      <div class="col period-id">
        <${TextInput} value=${pid} name="pid_${pk}" onInput=${setPid}
          error=${errors.pid} required />
      </div>
      <div class="col period-stream">
        <${StreamSelect} name="stream_${pk}" value=${stream}
          onChange=${setStream} error=${errors.stream} />
      </div>
      <div class="col period-start">
        <${TimeDeltaInput} value=${start} name="start_${pk}"
          onChange=${setField} error=${errors.start} />
      </div>
      <div class="col period-duration">
        <${TimeDeltaInput} value=${duration} name="duration_${pk}"
          onChange=${setField} min="00:00:01" error=${errors.duration} />
      </div>
      <div class="col period-tracks">
        <a class="btn btn-sm m-1 ${numTracks === 'choose' ? 'btn-warning' : 'btn-success'}"
          onClick=${selectTracks}>${ numTracks }
        </a>
      </div>
    </li>`;
}

export function PeriodsTable({errors}) {
  const { model, modified } = useContext(PageStateContext);
  const periods = useComputed(() => model.value?.periods ?? []);
  const errorsDiv = useComputed(() => {
    if (errors.value.periods === undefined) {
      return null;
    }
    return html`<${Alert} text=${errors.value.periods} level="warning" />`;
  });

  const setPeriodOrder = useCallback((items) => {
    const pks = items.map(prd => prd.pk);
    model.value = setOrdering(model.value, pks);
    modified.value = true;
  }, [model, modified]);

  const addPeriodBtn = useCallback((ev) => {
    ev.preventDefault();
    console.log('add period');
    model.value = addPeriod(model.value);
    modified.value = true;
  }, [model, modified]);

  const renderItem = (props) => {
    return html`<${PeriodRow} ...${props} addPeriod=${addPeriodBtn} />`;
  }

  return html`
    <div class="period-table border">
      <div class="row bg-secondary text-white table-head">
          <div class="col period-ordering">#</div>
          <div class="col period-id">ID</div>
          <div class="col period-stream">Stream</div>
          <div class="col period-start">Start Time</div>
          <div class="col period-duration">Duration</div>
          <div class="col period-tracks">Tracks</div>
      </div>
      <${Sortable} Component="ul" items=${periods} setItems=${setPeriodOrder} RenderItem=${renderItem} dataKey="pk" />
      <div class="btn-toolbar">
        <button class="btn btn-primary btn-sm m-2" onClick=${addPeriodBtn} >Add a Period</button>
      </div>
    </div>
    ${ errorsDiv.value }`;
}
