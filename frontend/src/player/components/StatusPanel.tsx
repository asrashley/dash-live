import { useComputed, type ReadonlySignal } from "@preact/signals";
import { StatusEvent } from "../types/StatusEvent";
import { createTimeObject, timeObjectToString } from "../utils/formatTimecode";

function StatusRow({ timecode, text }: StatusEvent) {
  return (
    <p>
      <span className="timecode">{timecode}</span>: {text}
    </p>
  );
}

export interface StatusPanelProps {
  events: ReadonlySignal<StatusEvent[]>;
  currentTime: ReadonlySignal<number>;
}

export function StatusPanel({ events, currentTime }: StatusPanelProps) {
  const timecode = useComputed<string>(() =>
    timeObjectToString(createTimeObject(currentTime.value))
  );
  return (
    <div id="status">
      {events.value.map((evt) => (
        <StatusRow key={evt.id} {...evt} />
      ))}
      <span className="timecode">{timecode}</span>
    </div>
  );
}
