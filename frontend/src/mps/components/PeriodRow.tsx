import { Fragment, type JSX } from "preact";
import { useComputed, useSignal } from "@preact/signals";
import { useContext, useCallback } from "preact/hooks";

import { AppStateContext } from "../../appState";
import { TextInput } from "../../form/components/TextInput";
import { TimeDeltaInput } from "../../form/components/TimeDeltaInput";
import { AllStreamsContext } from "../../hooks/useAllStreams";
import { MultiPeriodModelContext, MpsPeriodValidationErrors, UseMultiPeriodStreamHook } from "../../hooks/useMultiPeriodStream";
import { PeriodRowProps } from "../types/PeriodRowProps";
import { PeriodOrder } from "./PeriodOrder";
import { StreamSelection } from "./StreamSelection";
import { TrackSelectionButton } from "./TrackSelectionButton";
import { DecoratedStream } from "../../types/DecoratedStream";
import { MpsTrack } from "../../types/MpsTrack";

function setPeriodStream(periodPk: string | number, stream: DecoratedStream, currentTracks: MpsTrack[], modifyPeriod: UseMultiPeriodStreamHook["modifyPeriod"]) {
  let tracks: MpsTrack[] = [...currentTracks];
  const tids = new Set(tracks.map((tk) => tk.track_id));
  const activeContent = new Set(
    tracks.filter((tk) => tk.enabled).map((tk) => tk.content_type)
  );
  const streamTracks = new Set<number>();
  stream.tracks.forEach((tk) => {
    streamTracks.add(tk.track_id);
    if (!tids.has(tk.track_id)) {
      const newTk: MpsTrack = {
        lang: null,
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

export function PeriodRow({ period }: PeriodRowProps) {
  const { streamsMap } = useContext(AllStreamsContext);
  const { dialog } = useContext(AppStateContext);
  const { errors, modifyPeriod, addPeriod, removePeriod } = useContext(
    MultiPeriodModelContext
  );
  const prdErrors = useComputed<MpsPeriodValidationErrors>(() => {
    if (!errors.value) {
      return {};
    }
    return errors.value?.periods?.[period.pid] ?? {};
  });
  const pidError = useComputed(() => prdErrors.value.pid);
  const currentStream = useComputed(() => streamsMap.value.get(`${period.stream}`));
  const start = useSignal<string>(period.start);
  const duration = useSignal<string>(period.duration);
  const startError = useComputed<string | undefined>(() => prdErrors.value.start);
  const durationError = useComputed<string | undefined>(() => prdErrors.value.duration);
  const streamSelectionError = useComputed<string | undefined>(() => prdErrors.value.stream);
  const { pid, pk } = period;

  const selectTracks = useCallback(() => {
    const stream = currentStream.value;
    if (!stream) {
      return;
    }
    dialog.value = {
      backdrop: true,
      trackPicker: {
        pk,
        pid,
        guest: false,
        stream,
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
    ({ value }: {name: string, value: number}) => {
      const stream = streamsMap.value.get(`${value}`);
      if (stream){
        setPeriodStream(pk, stream, period.tracks, modifyPeriod);
      }
    },
    [modifyPeriod, period, pk, streamsMap]
  );

  const deletePeriodBtn = useCallback(() => {
    removePeriod(pk);
  }, [pk, removePeriod]);

  return <Fragment>
    <div className="col period-ordering">
      <PeriodOrder addPeriod={addPeriod} deletePeriod={deletePeriodBtn} />
    </div>
    <div className="col period-id">
      <TextInput
        value={pid}
        name={`pid_${pk}`}
        onInput={setPid}
        error={pidError}
        required />
    </div>
    <div class="col period-stream">
      <StreamSelection
        name={`stream_${pk}`}
        value={currentStream}
        onChange={setStream}
        error={streamSelectionError}
        required />
    </div>
    <div class="col period-start">
      <TimeDeltaInput
        value={start}
        name={`start_${pk}`}
        onChange={setField}
        error={startError}
        required />
    </div>
    <div class="col period-duration">
      <TimeDeltaInput
        value={duration}
        name={`duration_${pk}`}
        onChange={setField}
        min="00:00:01"
        error={durationError}
        required />
    </div>
    <TrackSelectionButton period={period} stream={currentStream} selectTracks={selectTracks} />
  </Fragment>;
}
