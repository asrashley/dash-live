import { type JSX } from "preact";
import { useComputed } from "@preact/signals";
import { useContext, useCallback } from "preact/hooks";

import { AppStateContext } from "../../appState";
import { TextInput } from "../../components/TextInput";
import { TimeDeltaInput } from "../../components/TimeDeltaInput";
import { AllStreamsContext } from "../../hooks/useAllStreams";
import { MultiPeriodModelContext, MpsPeriodValidationErrors, UseMultiPeriodStreamHook } from "../../hooks/useMultiPeriodStream";
import { PeriodRowProps } from "../types/PeriodRowProps";
import { PeriodOrder } from "./PeriodOrder";
import { rowColours } from "./rowColours";
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

export function PeriodRow({ className = "", index, item: period }: PeriodRowProps) {
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
    ({ value }: {name: string, value: number}) => {
      const stream = streamsMap.value.get(`${value}`);
      setPeriodStream(pk, stream, period.tracks, modifyPeriod);
    },
    [modifyPeriod, period, pk, streamsMap]
  );

  const deletePeriodBtn = useCallback(() => {
    removePeriod(pk);
  }, [pk, removePeriod]);

  const clsNames = `row mt-1 p-1 ${rowColours[index % rowColours.length]} ${className}`;

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
        required />
    </div>
    <div class="col period-stream">
      <StreamSelection
        name={`stream_${pk}`}
        value={currentStream}
        onChange={setStream}
        error={prdErrors.value.stream}
        required />
    </div>
    <div class="col period-start">
      <TimeDeltaInput
        value={start}
        name={`start_${pk}`}
        onChange={setField}
        error={prdErrors.value.start}
        required />
    </div>
    <div class="col period-duration">
      <TimeDeltaInput
        value={duration}
        name={`duration_${pk}`}
        onChange={setField}
        min="00:00:01"
        error={prdErrors.value.duration}
        required />
    </div>
    <TrackSelectionButton period={period} stream={currentStream} selectTracks={selectTracks} />
  </li>;
}
