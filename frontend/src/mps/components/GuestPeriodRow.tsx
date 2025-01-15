import { useContext } from "preact/hooks";

import { AppStateContext } from "../../appState";
import { TimeDeltaInput } from "../../components/TimeDeltaInput";
import { AllStreamsContext } from "../../hooks/useAllStreams";
import { PeriodRowProps } from "../types/PeriodRowProps";
import { rowColours } from "./rowColours";
import { TrackSelectionButton } from "./TrackSelectionButton";

function doNothing() {
}

export function GuestPeriodRow({ index, item, className = "" }: PeriodRowProps) {
  const { ordering, pid, pk, start, duration } = item;
  const { streamsMap } = useContext(AllStreamsContext);
  const { dialog } = useContext(AppStateContext);
  const stream = streamsMap.value.get(`${item.stream}`);
  const selectTracks = () => {
    dialog.value = {
      backdrop: true,
      trackPicker: {
        pk,
        pid,
        guest: true,
        stream,
      },
    };
  };
  const clsNames = `row mt-1 p-1 ${rowColours[index % rowColours.length]} ${className}`;

  return <li className={clsNames}>
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
    <TrackSelectionButton period={item} stream={stream} selectTracks={selectTracks} />
  </li>;
}
