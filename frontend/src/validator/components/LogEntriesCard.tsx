import { UseValidatorWebsocketHook } from "../hooks/useValidatorWebsocket";
import { LogEntry } from "../types/LogEntry";

function LogLine({ text, level }: LogEntry) {
  return <p className={level}>{text}</p>;
}

export interface LogEntriesCardProps {
  log: UseValidatorWebsocketHook["log"];
}

export function LogEntriesCard({ log }: LogEntriesCardProps) {
  return (
    <div className="card results">
      {log.value.map((msg) => (
        <LogLine key={msg.id} {...msg} />
      ))}
    </div>
  );
}
