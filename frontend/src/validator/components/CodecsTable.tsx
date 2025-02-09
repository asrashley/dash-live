import { useComputed, type ReadonlySignal } from "@preact/signals";

import { CodecDetails, CodecInformation } from "../types/CodecInformation";

function CodecDetailsCell({ details, error, label }: CodecDetails) {
  if (error) {
    return <p className="codec-error fw-bold">{error}</p>;
  }
  return (
    <div>
      <p class="codec-item fw-bold">{label}</p>
      {details.map((item) => (
        <p key={item} className="codec-item">{item}</p>
      ))}
    </div>
  );
}

function CodecRow({ codec, details }: CodecInformation) {
  return (
    <tr>
      <td className="codec-string">{codec}</td>
      <td className="codec-detail">
        {details.map((det) => (
          <CodecDetailsCell key={det.label} {...det} />
        ))}
      </td>
    </tr>
  );
}

interface CodecsTableProps {
  codecs: ReadonlySignal<CodecInformation[]>;
}

export function CodecsTable({ codecs }: CodecsTableProps) {
  const className = useComputed<string>(() =>
    codecs.value.length === 0 ? "d-none" : "table table-striped manifest-codecs"
  );
  return (
    <table className={className}>
      <thead>
        <tr>
          <th class="codec-string">Codec</th>
          <th class="codec-detail">Details</th>
        </tr>
      </thead>
      <tbody>
        {codecs.value.map((info) => (
          <CodecRow key={info.codec} {...info} />
        ))}
      </tbody>
    </table>
  );
}
