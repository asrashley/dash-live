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
import { MultiPeriodModelContext } from '../../hooks/useMultiPeriodStream.js';
import { AllStreamsContext } from '../../hooks/useAllStreams.js';

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
  const { allStreams } = useContext(AllStreamsContext);
  const streams = useComputed(() => allStreams.value ?? []);

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
  ${ streams.value.map(s => html`<option value=${s.pk}>${s.title}</option>`) }
</select>`;
}

const rowColours = ['bg-secondary-subtle', 'bg-primary-subtle'];

function doNothing(ev) {
  ev.preventDefault();
  return false;
}

function tracksDescription(tracks) {
  const count = Object.keys(tracks).length;
  if (count === 0) {
    return 'choose';
  }
  if (count === 1) {
    return '1 track';
  }
  return `${count} tracks`;
}

function GuestPeriodRow({index, item, className=""}) {
  const { ordering, pid, pk, start, duration, tracks } = item;
  const { streamsMap } = useContext(AllStreamsContext);
  const { dialog }  = useContext(AppStateContext);
  const numTracks = useMemo(() => tracksDescription(tracks), [tracks]);
  const stream = useComputed(() => streamsMap.value.get(item.stream));
  const selectTracks = useCallback(() => {
    dialog.value = {
      backdrop: true,
      trackPicker: {
        pk,
        pid,
        guest: true,
        stream: stream.value,
      },
    };
  }, [dialog, pid, pk, stream]);
  const clsNames = `row mt-1 p-1 ${rowColours[index % rowColours.length]} ${className}`;

  return html`<li class="${clsNames}">
      <div class="col period-ordering">${ordering}</div>
      <div class="col period-id">${pid}</div>
      <div class="col period-stream">${stream.value.title}</div>
      <div class="col period-start">
        <${TimeDeltaInput} value=${start} name="start_${pk}"
          onChange=${doNothing}  disabled />
      </div>
      <div class="col period-duration">
        <${TimeDeltaInput} value=${duration} name="duration_${pk}"
          onChange=${doNothing} disabled />
      </div>
      <div class="col period-tracks">
        <a class="btn btn-sm m-1 btn-primary" onClick=${selectTracks}>${numTracks}</a>
      </div>
    </li>`;
}

function PeriodRow({className="", index, item: period, ...props}) {
  const { streamsMap } = useContext(AllStreamsContext);
  const { dialog }  = useContext(AppStateContext);
  const { errors, modifyPeriod, addPeriod, removePeriod } = useContext(MultiPeriodModelContext);
  const numTracks = useMemo(() => tracksDescription(period.tracks), [period.tracks]);
  const { pid, pk, stream, start, duration } = period;

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
    modifyPeriod({
      periodPk: pk,
      period: {
        pid: ev.target.value,
      }
    });
  }, [modifyPeriod, pk]);

  const setField = useCallback(({name, value}) => {
    const fieldName = name.split('_')[0];
    modifyPeriod({
      periodPk: pk,
      period: {
        [fieldName]: value,
      }
    });
  }, [modifyPeriod, pk]);

  const setStream = useCallback(({value}) => {
    const stream = streamsMap.value.get(value);

    modifyPeriod({
      periodPk: pk,
      period: {
        stream: value,
        duration: stream.duration,
      },
    });
  }, [modifyPeriod, pk, streamsMap.value])

  const deletePeriodBtn = useCallback(() => {
    removePeriod(pk);
  }, [pk, removePeriod]);

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
          onChange=${setStream} error=${errors.stream} required />
      </div>
      <div class="col period-start">
        <${TimeDeltaInput} value=${start} name="start_${pk}"
          onChange=${setField} error=${errors.start} required />
      </div>
      <div class="col period-duration">
        <${TimeDeltaInput} value=${duration} name="duration_${pk}"
          onChange=${setField} min="00:00:01" error=${errors.duration} required />
      </div>
      <div class="col period-tracks">
        <a class="btn btn-sm m-1 ${numTracks === 'choose' ? 'btn-warning' : 'btn-success'}"
          onClick=${selectTracks}>${ numTracks }
        </a>
      </div>
    </li>`;
}

function ButtonToolbar({onAddPeriod}) {
  const { user } = useContext(AppStateContext);
  if (!user.value.permissions.media) {
    return null;
  }
  return html`<div class="btn-toolbar">
    <button class="btn btn-primary btn-sm m-2" onClick=${onAddPeriod} >
      Add a Period
    </button>
  </div>`;
}

export function PeriodsTable() {
  const { user } = useContext(AppStateContext);
  const { errors, model, addPeriod, setOrdering } = useContext(MultiPeriodModelContext);
  const periods = useComputed(() => model.value?.periods ?? []);
  const errorsDiv = useComputed(() => {
    if (errors.value.periods === undefined) {
      return null;
    }
    return Object.values(errors.value.periods).map(err =>
      html`<${Alert} text=${err} level="warning" />`);
  });

  const setPeriodOrder = useCallback((items) => {
    const pks = items.map(prd => prd.pk);
    setOrdering(pks);
  }, [setOrdering]);

  const addPeriodBtn = useCallback((ev) => {
    ev.preventDefault();
    addPeriod();
  }, [addPeriod]);

  const renderItem = useCallback((props) => {
    if (!user.value.permissions.media) {
      return html`<${GuestPeriodRow} ...${props} />`;
    }
    return html`<${PeriodRow} ...${props} addPeriod=${addPeriodBtn} />`;
  }, [addPeriodBtn, user.value.permissions.media]);

  return html`<div>
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
      <${ButtonToolbar} onAddPeriod=${addPeriodBtn} />
    </div>
    ${ errorsDiv.value }
  </div>`;
}
