import { Fragment } from "preact";
import { useCallback, useContext } from "preact/hooks";

import { AppStateContext } from "../../appState";
import { TimeDeltaInput } from "../../components/TimeDeltaInput";
import { AllStreamsContext } from "../../hooks/useAllStreams";
import { PeriodRowProps } from "../types/PeriodRowProps";
import { TrackSelectionButton } from "./TrackSelectionButton";

function doNothing() {
}

export function GuestPeriodRow({ period }: PeriodRowProps) {
  const { ordering, pid, pk, start, duration } = period;
  const { streamsMap } = useContext(AllStreamsContext);
  const { dialog } = useContext(AppStateContext);
  const stream = streamsMap.value.get(`${period.stream}`);
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

  return <Fragment>
    <div className="col period-ordering">{ordering}</div>
    <div className="col period-id">{pid}</div>
    <div className="col period-stream">{stream?.title}</div>
    <div className="col period-start">
      <TimeDeltaInput
        value={start}
        name={`start_${pk}`}
        onChange={doNothing}
        disabled />
    </div>
    <div class="col period-duration">
      <TimeDeltaInput
        value={duration}
        name={`duration_${pk}`}
        onChange={doNothing}
        disabled />
    </div>
    <TrackSelectionButton period={period} stream={stream} selectTracks={selectTracks} />
  </Fragment>;
}
