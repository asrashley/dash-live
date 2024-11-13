import { html } from "htm/preact";
import { useCallback, useContext, useMemo } from "preact/hooks";
import { useComputed } from "@preact/signals";

import {
  Alert,
  DropDownMenu,
  Icon,
  Sortable,
  TextInput,
  TimeDeltaInput,
} from "@dashlive/ui";
import { AllStreamsContext, MultiPeriodModelContext } from "@dashlive/hooks";
import { AppStateContext } from "../../appState.js";

function PeriodOrder({ addPeriod, deletePeriod }) {
  const menu = [
    {
      title: "Add another Period",
      onClick: addPeriod,
    },
    {
      title: "Delete Period",
      onClick: deletePeriod,
    },
  ];

  return html`<${DropDownMenu} linkClass="" menu=${menu}>
    <${Icon} name="three-dots" />
  <//>`;
}

function StreamSelect({ value, onChange, name }) {
  const { allStreams } = useContext(AllStreamsContext);
  const streams = useComputed(() => allStreams.value ?? []);

  const changeHandler = useCallback(
    (ev) => {
      onChange({
        name,
        value: parseInt(ev.target.value, 10),
      });
    },
    [onChange, name]
  );

  return html` <select
    class="form-select"
    value=${value}
    name=${name}
    onChange=${changeHandler}
  >
    <option value="">--Select a stream--</option>
    ${streams.value.map((s) => html`<option value=${s.pk}>${s.title}</option>`)}
  </select>`;
}

const rowColours = ["bg-secondary-subtle", "bg-primary-subtle"];

function doNothing(ev) {
  ev.preventDefault();
  return false;
}

function tracksDescription(tracks) {
  const enabledCount = tracks.filter(tk => tk.enabled).length;
  if (tracks.length === 0) {
    return "----";
  }
  if (tracks.length === 1) {
    return "1 track";
  }
  return `${enabledCount}/${tracks.length} tracks`;
}

function GuestPeriodRow({ index, item, className = "" }) {
  const { ordering, pid, pk, start, duration, tracks } = item;
  const { streamsMap } = useContext(AllStreamsContext);
  const { dialog } = useContext(AppStateContext);
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
  const clsNames = `row mt-1 p-1 ${
    rowColours[index % rowColours.length]
  } ${className}`;

  return html`<li class="${clsNames}">
    <div class="col period-ordering">${ordering}</div>
    <div class="col period-id">${pid}</div>
    <div class="col period-stream">${stream.value.title}</div>
    <div class="col period-start">
      <${TimeDeltaInput}
        value=${start}
        name="start_${pk}"
        onChange=${doNothing}
        disabled
      />
    </div>
    <div class="col period-duration">
      <${TimeDeltaInput}
        value=${duration}
        name="duration_${pk}"
        onChange=${doNothing}
        disabled
      />
    </div>
    <div class="col period-tracks">
      <a class="btn btn-sm m-1 btn-primary" onClick=${selectTracks}
        >${numTracks}</a
      >
    </div>
  </li>`;
}

function setPeriodStream(periodPk, stream, currentTracks, modifyPeriod) {
  let tracks = [...currentTracks];
  const tids = new Set(tracks.map((tk) => tk.track_id));
  const activeContent = new Set(
    tracks.filter((tk) => tk.enabled).map((tk) => tk.content_type)
  );
  const streamTracks = new Set();
  stream.tracks.forEach((tk) => {
    streamTracks.add(tk.track_id);
    if (!tids.has(tk.track_id)) {
      const newTk = {
        ...tk,
        role: activeContent.has(tk.content_type) ? "alternate": "main",
        enabled: !activeContent.has(tk.content_type),
        encrypted: false,
      };
      if (newTk.enabled) {
        activeContent.add(newTk.content_type);
      }
      tracks.push(newTk);
    }
  });
  tracks = tracks.filter(tk => streamTracks.has(tk.track_id));
  tracks.sort((a, b) => a.track_id - b.track_id);

  modifyPeriod({
    periodPk,
    period: {
      stream: stream.pk,
      duration: stream.duration,
    },
    tracks,
  });
}

function PeriodRow({ className = "", index, item: period, ...props }) {
  const { streamsMap } = useContext(AllStreamsContext);
  const { dialog } = useContext(AppStateContext);
  const { errors, modifyPeriod, addPeriod, removePeriod } = useContext(
    MultiPeriodModelContext
  );
  const trackBtnLabel = useMemo(
    () => tracksDescription(period.tracks),
    [period.tracks]
  );
  const numActiveTracks = useMemo(
    () => period.tracks.filter(tk => tk.enabled).length,
  [period.tracks]);
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

  const setPid = useCallback(
    (ev) => {
      modifyPeriod({
        periodPk: pk,
        period: {
          pid: ev.target.value,
        },
      });
    },
    [modifyPeriod, pk]
  );

  const setField = useCallback(
    ({ name, value }) => {
      const fieldName = name.split("_")[0];
      modifyPeriod({
        periodPk: pk,
        period: {
          [fieldName]: value,
        },
      });
    },
    [modifyPeriod, pk]
  );

  const setStream = useCallback(
    ({ value }) => {
      const stream = streamsMap.value.get(value);
      setPeriodStream(pk, stream, period.tracks, modifyPeriod);
    },
    [modifyPeriod, period.tracks, pk, streamsMap]
  );

  const deletePeriodBtn = useCallback(() => {
    removePeriod(pk);
  }, [pk, removePeriod]);

  const clsNames = `row mt-1 p-1 ${
    rowColours[index % rowColours.length]
  } ${className}`;

  return html` <li class="${clsNames}" ...${props}>
    <div class="col period-ordering">
      <${PeriodOrder} addPeriod=${addPeriod} deletePeriod=${deletePeriodBtn} />
    </div>
    <div class="col period-id">
      <${TextInput}
        value=${pid}
        name="pid_${pk}"
        onInput=${setPid}
        error=${errors.pid}
        required
      />
    </div>
    <div class="col period-stream">
      <${StreamSelect}
        name="stream_${pk}"
        value=${stream}
        onChange=${setStream}
        error=${errors.stream}
        required
      />
    </div>
    <div class="col period-start">
      <${TimeDeltaInput}
        value=${start}
        name="start_${pk}"
        onChange=${setField}
        error=${errors.start}
        required
      />
    </div>
    <div class="col period-duration">
      <${TimeDeltaInput}
        value=${duration}
        name="duration_${pk}"
        onChange=${setField}
        min="00:00:01"
        error=${errors.duration}
        required
      />
    </div>
    <div class="col period-tracks">
      <a
        class="btn btn-sm m-1 ${numActiveTracks === 0
          ? "btn-warning"
          : "btn-success"}"
        onClick=${selectTracks}
        >${trackBtnLabel}
      </a>
    </div>
  </li>`;
}

function ButtonToolbar({ onAddPeriod }) {
  const { user } = useContext(AppStateContext);
  if (!user.value.permissions.media) {
    return null;
  }
  return html`<div class="btn-toolbar">
    <button class="btn btn-primary btn-sm m-2" onClick=${onAddPeriod}>
      Add a Period
    </button>
  </div>`;
}

export function PeriodsTable() {
  const { user } = useContext(AppStateContext);
  const { errors, model, addPeriod, setPeriodOrdering } = useContext(
    MultiPeriodModelContext
  );
  const periods = useComputed(() => model.value?.periods ?? []);
  const errorList = useComputed(() => {
    if (errors.value.periods === undefined) {
      return [];
    }
    return Object.entries(errors.value.periods).map(([pid, err]) => {
      if (pid === "_") {
        return err;
      }
      return `${pid}: ${Object.values(err).join(". ")}`;
    });
  });

  const setPeriodOrder = useCallback(
    (items) => {
      const pks = items.map((prd) => prd.pk);
      setPeriodOrdering(pks);
    },
    [setPeriodOrdering]
  );

  const addPeriodBtn = useCallback(
    (ev) => {
      ev.preventDefault();
      addPeriod();
    },
    [addPeriod]
  );

  const renderItem = useCallback(
    (props) => {
      if (!user.value.permissions.media) {
        return html`<${GuestPeriodRow} ...${props} />`;
      }
      return html`<${PeriodRow} ...${props} addPeriod=${addPeriodBtn} />`;
    },
    [addPeriodBtn, user.value.permissions.media]
  );

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
      <${Sortable}
        Component="ul"
        items=${periods}
        setItems=${setPeriodOrder}
        RenderItem=${renderItem}
        dataKey="pk"
      />
      <${ButtonToolbar} onAddPeriod=${addPeriodBtn} />
    </div>
    ${errorList.value.map(
      (err) => html`<${Alert} text="${err}" level="warning" />`
    )}
  </div>`;
}
