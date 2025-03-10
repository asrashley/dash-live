import { useComputed, type ReadonlySignal } from "@preact/signals";
import { StatusEvent } from "../types/StatusEvent";
import { createTimeObject, timeObjectToString } from "../utils/formatTimecode";

function StatusRow({ event, timecode, text }: StatusEvent) {
  return (
    <p class="status-row">
      <span className="timecode">{timecode}</span>{event} {text}
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
      <div className="play-position">{timecode}</div>
    </div>
  );
}
