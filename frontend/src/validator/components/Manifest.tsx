import { type ReadonlySignal } from "@preact/signals";
import { ManifestLine } from "../types/ManifestLine";

function ManifestRow({ text, line, hasError, errors }: ManifestLine) {
  const className = `manifest-line${hasError ? " error" : ""}`;
  return (
    <div className={className} id={`mpd-line-${line}`}>
      <span className="line-num">{line}</span>
      <pre className="text">{text}</pre>
      {errors.map((err, idx) => (
        <p key={idx} className="error-text">
          {err}
        </p>
      ))}
    </div>
  );
}

interface ManifestProps {
  manifest: ReadonlySignal<ManifestLine[]>;
}

export function Manifest({ manifest }: ManifestProps) {
  return (
    <div className="card" id="manifest-text">
      {manifest.value.map((row) => (
        <ManifestRow key={row.line} {...row} />
      ))}
    </div>
  );
}
