import { useComputed, useSignal, type ReadonlySignal } from "@preact/signals";
import { ManifestLine } from "../types/ManifestLine";
import { HorizontalScroller } from "./HorizontalScroller";

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
  maxHeight?: number;
  minHeight?: number;
}

export function Manifest({ manifest, minHeight=5, maxHeight=50 }: ManifestProps) {
  const left = useSignal<number>(0);
  const scrollHeight = useComputed<string>(() => {
    const lines = manifest.value.length;
    const height = Math.min(Math.max(lines, minHeight), maxHeight);
    return `${height}em`;
  });

  return (
    <div className="card" id="manifest-text">
      <HorizontalScroller height={scrollHeight} width="150em" left={left}>
        {manifest.value.map((row) => (
          <ManifestRow key={row.line} {...row} />
        ))}
      </HorizontalScroller>
    </div>
  );
}
