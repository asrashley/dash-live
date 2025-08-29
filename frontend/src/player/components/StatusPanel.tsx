import { type ReadonlySignal } from "@preact/signals";
import { StatusEvent } from "../types/StatusEvent";

function StatusRow({ event, timecode, text }: StatusEvent) {
  return (
    <p class="status-row">
      <span className="timecode">{timecode}</span>{event} {text}
    </p>
  );
}

export interface StatusPanelProps {
  events: ReadonlySignal<StatusEvent[]>;
}

export function StatusPanel({ events }: StatusPanelProps) {
  return (
    <div id="status">
      {events.value.map((evt) => (
        <StatusRow key={evt.id} {...evt} />
      ))}
    </div>
  );
}
