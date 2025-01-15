import { type JSX } from "preact";
import { useCallback, useContext } from "preact/hooks";
import { useComputed } from "@preact/signals";

import { Alert } from '../../components/Alert';
import { RenderItemProps, SortableList } from '../../components/SortableList';
import { TextInput } from '../../components/TextInput';
import { TimeDeltaInput }  from '../../components/TimeDeltaInput';

import { AllStreamsContext } from '../../hooks/useAllStreams';
import { MpsPeriodValidationErrors, MultiPeriodModelContext } from '../../hooks/useMultiPeriodStream';
import { AppStateContext } from "../../appState";
import { MpsPeriod } from "../../types/MpsPeriod";
import { MpsTrack } from "../../types/MpsTrack";
import { DecoratedStream } from "../../types/DecoratedStream";
import { PeriodOrder } from "./PeriodOrder";


interface StreamSelectProps {
  value?: DecoratedStream,
  onChange: (props: {name: string, value: number}) => void;
  name: string;
  error?: string;
  required?: boolean;
 }
function StreamSelect({ value, onChange, name, error, required }: StreamSelectProps) {
  const { allStreams } = useContext(AllStreamsContext);
  const streams = useComputed(() => allStreams.value ?? []);
  const validationClass = error
    ? " is-invalid"
    : value
    ? " is-valid"
    : "";
  const className = `form-select${validationClass}`;

  const changeHandler = useCallback(
    (ev) => {
      onChange({
        name,
        value: parseInt(ev.target.value, 10),
      });
    },
    [onChange, name]
  );

  return <select
    className={className}
    value={value?.pk}
    name={name}
    onChange={changeHandler}
    required={required}
  >
    <option value="">--Select a stream--</option>
    {streams.value.map((s) => <option key={s.pk} value={s.pk}>{s.title}</option>)}
  </select>;
}

const rowColours = ["bg-secondary-subtle", "bg-primary-subtle"];

function doNothing() {
}

function tracksDescription(tracks: MpsTrack[], stream) {
  const enabledCount = tracks.filter(tk => tk.enabled).length;
  const numTracks = stream?.tracks.length ?? 0;
  if (numTracks === 0) {
    return "----";
  }
  if (tracks.length === 1 && numTracks === 1) {
    return "1 track";
  }
  return `${enabledCount}/${numTracks} tracks`;
}

interface TrackSelectionButtonProps {
  period?: MpsPeriod,
  stream,
  selectTracks: (ev: Event) => void;
}
function TrackSelectionButton({ period, stream, selectTracks }: TrackSelectionButtonProps) {
  if (!period) {
    return <div className="col period-tracks" />;
  }
  const { tracks } = period;
  const description = tracksDescription(tracks, stream);
  const hasActiveTracks = tracks.some(tk => tk.enabled);
  const disabled = stream === undefined;
  const className = `btn btn-sm m-1 ${hasActiveTracks ? "btn-success" : "btn-warning"}${disabled ? ' disabled': ''}`;

  return <div className="col period-tracks">
  <a className={className} onClick={selectTracks} aria-disabled={disabled}>
    {description}
  </a>
</div>;
}

interface PeriodRowProps {
  className?: string;
  index: number;
  item: MpsPeriod;
}

function GuestPeriodRow({ index, item, className }: PeriodRowProps) {
  const { ordering, pid, pk, start, duration } = item;
  const { streamsMap } = useContext(AllStreamsContext);
  const { dialog } = useContext(AppStateContext);
  const stream = streamsMap.value.get(`${item.stream}`);
  const selectTracks = useCallback(() => {
    dialog.value = {
      backdrop: true,
      trackPicker: {
        pk,
        pid,
        guest: true,
        stream,
      },
    };
  }, [dialog, pid, pk, stream]);
  const clsNames = `row mt-1 p-1 ${
    rowColours[index % rowColours.length]
  } ${className ?? ""}`;

  return <li className={clsNames}>
    <div className="col period-ordering">{ordering}</div>
    <div className="col period-id">{pid}</div>
    <div className="col period-stream">{stream?.title}</div>
    <div className="col period-start">
      <TimeDeltaInput
        value={start}
        name={`start_${pk}`}
        onChange={doNothing}
        disabled
      />
    </div>
    <div class="col period-duration">
      <TimeDeltaInput
        value={duration}
        name="duration_${pk}"
        onChange={doNothing}
        disabled
      />
    </div>
    <TrackSelectionButton period={item} stream={stream} selectTracks={selectTracks} />
  </li>;
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

function PeriodRow({ className = "", index, item: period }: PeriodRowProps) {
  const { streamsMap } = useContext(AllStreamsContext);
  const { dialog } = useContext(AppStateContext);
  const { errors, modifyPeriod, addPeriod, removePeriod } = useContext(
    MultiPeriodModelContext
  );
  const prdErrors = useComputed<MpsPeriodValidationErrors>(() => errors?.[period?.pid] ?? {});
  const currentStream = streamsMap.value.get(`${period.stream}`);
  const { pid, pk, start, duration } = period;

  const selectTracks = useCallback(() => {
    if (currentStream === undefined) {
      return;
    }
    dialog.value = {
      backdrop: true,
      trackPicker: {
        pk,
        pid,
        guest: false,
        stream: currentStream,
      },
    };
  }, [dialog, pid, pk, currentStream]);

  const setPid = useCallback(
    (ev: JSX.TargetedEvent<HTMLInputElement>) => {
      modifyPeriod({
        periodPk: pk,
        period: {
          pid: (ev.target as HTMLInputElement).value,
        },
      });
    },
    [modifyPeriod, pk]
  );

  const setField = useCallback(
    (name: string, value: string) => {
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
      if (period) {
        setPeriodStream(pk, stream, period.tracks, modifyPeriod);
      }
    },
    [modifyPeriod, period, pk, streamsMap]
  );

  const deletePeriodBtn = useCallback(() => {
    removePeriod(pk);
  }, [pk, removePeriod]);

  const clsNames = `row mt-1 p-1 ${
    rowColours[index % rowColours.length]
  } ${className}`;

  return <li className={clsNames}>
    <div className="col period-ordering">
      <PeriodOrder addPeriod={addPeriod} deletePeriod={deletePeriodBtn} />
    </div>
    <div className="col period-id">
      <TextInput
        value={pid}
        name={`pid_${pk}`}
        onInput={setPid}
        error={prdErrors.value.pid}
        required
      />
    </div>
    <div class="col period-stream">
      <StreamSelect
        name={`stream_${pk}`}
        value={currentStream}
        onChange={setStream}
        error={prdErrors.value.stream}
        required
      />
    </div>
    <div class="col period-start">
      <TimeDeltaInput
        value={start}
        name={`start_${pk}`}
        onChange={setField}
        error={prdErrors.value.start}
        required
      />
    </div>
    <div class="col period-duration">
      <TimeDeltaInput
        value={duration}
        name={`duration_${pk}`}
        onChange={setField}
        min="00:00:01"
        error={prdErrors.value.duration}
        required
      />
    </div>
    <TrackSelectionButton period={period} stream={currentStream} selectTracks={selectTracks} />
  </li>;
}

interface ButtonToolbarProps {
  onAddPeriod: (ev: Event) => void;
}

function ButtonToolbar({ onAddPeriod }: ButtonToolbarProps) {
  const { user } = useContext(AppStateContext);
  if (!user.value.permissions.media) {
    return null;
  }
  return <div className="btn-toolbar">
    <button className="btn btn-primary btn-sm m-2" onClick={onAddPeriod}>
      Add a Period
    </button>
  </div>;
}

export function PeriodsTable() {
  const { user } = useContext(AppStateContext);
  const { errors, model, addPeriod, setPeriodOrdering } = useContext(
    MultiPeriodModelContext
  );
  const periods = useComputed<MpsPeriod[]>(() => model.value?.periods ?? []);
  const errorList = useComputed<string[]>(() => {
    const errs: string[] = Object.entries(errors.value.periods ?? []).map(([pid, err]) => {
      return `${pid}: ${Object.values(err).join(". ")}`;
    });
    if (errors.value.allPeriods) {
      errs.push(errors.value.allPeriods);
    }
    return errs;
  });

  const setPeriodOrder = useCallback(
    (items: MpsPeriod[]) => {
      const pks = items.map((prd: MpsPeriod) => prd.pk);
      setPeriodOrdering(pks);
    },
    [setPeriodOrdering]
  );

  const addPeriodBtn = useCallback(
    (ev: Event) => {
      ev.preventDefault();
      addPeriod();
    },
    [addPeriod]
  );

  const renderItem = useCallback(
    ({item, ...props}: RenderItemProps) => {
      const row = item as MpsPeriod;
      if (!user.value.permissions.media) {
        return <GuestPeriodRow {...props} item={row} />;
      }
      return <PeriodRow {...props} item={row} />;
    },
    [user.value.permissions.media]
  );

  return <div>
    <div className="period-table border">
      <div className="row bg-secondary text-white table-head">
        <div className="col period-ordering">#</div>
        <div className="col period-id">ID</div>
        <div className="col period-stream">Stream</div>
        <div className="col period-start">Start Time</div>
        <div className="col period-duration">Duration</div>
        <div className="col period-tracks">Tracks</div>
      </div>
      <SortableList
        items={periods}
        setItems={setPeriodOrder}
        RenderItem={renderItem}
        dataKey="pk"
      />
      <ButtonToolbar onAddPeriod={addPeriodBtn} />
    </div>
    {errorList.value.map(
      (err: string, index: number) => <Alert id={index} key={err} text={err} level="warning" />
    )}
  </div>;
}
