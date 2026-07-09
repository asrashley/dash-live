import { Fragment } from "preact";
import { useComputed } from "@preact/signals";
import { useCallback, useContext } from "preact/hooks";

import { AppStateContext } from "../../appState";
import { TimeDeltaInput } from "../../form/components/TimeDeltaInput";
import { AllStreamsContext } from "../../hooks/useAllStreams";
import { PeriodRowProps } from "../types/PeriodRowProps";
import { TrackSelectionButton } from "./TrackSelectionButton";

export function GuestPeriodRow({ period }: PeriodRowProps) {
  const { ordering, pid, pk } = period;
  const start = useComputed<string>(() => period.start);
  const duration = useComputed<string>(() => period.duration);
  const { streamsMap } = useContext(AllStreamsContext);
  const { dialog } = useContext(AppStateContext);
  const stream = useComputed(() => streamsMap.value.get(`${period.stream}`));
  const title = useComputed<string>(() => stream.value?.title ?? "Unknown Stream");
  const selectTracks = useCallback(() => {
    const selectedStream = stream.value;
    if (!selectedStream) {
      return;
    }
    dialog.value = {
      backdrop: true,
      trackPicker: {
        pk,
        pid,
        guest: true,
        stream: selectedStream,
      },
    };
  }, [dialog, pid, pk, stream]);

  return <Fragment>
    <div className="col period-ordering">{ordering}</div>
    <div className="col period-id">{pid}</div>
    <div className="col period-stream">{title}</div>
    <div className="col period-start">
      <TimeDeltaInput
        value={start}
        name={`start_${pk}`}
        disabled />
    </div>
    <div className="col period-duration">
      <TimeDeltaInput
        value={duration}
        name={`duration_${pk}`}
        disabled />
    </div>
    <TrackSelectionButton period={period} stream={stream} selectTracks={selectTracks} />
  </Fragment>;
}
