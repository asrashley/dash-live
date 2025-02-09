import { useComputed } from "@preact/signals";
import { UseValidatorWebsocketHook } from "../hooks/useValidatorWebsocket";
import { ErrorEntry } from "../types/ErrorEntry";

function ErrorRow({ assertion, location, msg, clause = "" }: ErrorEntry) {
  const { filename, line } = assertion;
  const [start] = location;
  return (
    <tr>
      <td class="lineno">{start}</td>
      <td class="clause">{clause}</td>
      <td class="message">{msg}</td>
      <td class="source-location">
        {filename}:{line}
      </td>
    </tr>
  );
}

interface ManifestErrorsTableProps {
  errors: UseValidatorWebsocketHook["errors"];
}

export function ManifestErrorsTable({ errors }: ManifestErrorsTableProps) {
  const className = useComputed<string>(() => `${ errors.value.length === 0 ? "d-none": "table table-striped manifest-errors"}`);
  return (
    <table className={className}>
      <thead>
        <tr>
          <th class="lineno">MPD line</th>
          <th class="clause">DASH clause</th>
          <th class="message">Error Details</th>
          <th class="source-location">Source code</th>
        </tr>
      </thead>
      <tbody>
        {errors.value.map((err, idx) => (
          <ErrorRow key={idx} {...err} />
        ))}
      </tbody>
    </table>
  );
}

