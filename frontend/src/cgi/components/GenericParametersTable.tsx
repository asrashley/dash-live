/* eslint-disable react/no-danger */
import { useCgiOptions } from "../../hooks/useCgiOptions";
import { CgiOptionDescription } from "../../types/CgiOptionDescription";
import { BooleanCell } from "./BooleanCell";

function GenericParametersRow({
  name,
  syntax,
  description,
  usage,
}: CgiOptionDescription) {
  return (
    <tr>
      <td className="parameter">
        {name}={syntax}
      </td>
      <td
        className="description"
        dangerouslySetInnerHTML={{ __html: description }}
      />
      <td className="manifest">
        <BooleanCell value={usage.includes("manifest")} />
      </td>
      <td className="video">
        <BooleanCell value={usage.includes("video")} />
      </td>
      <td className="audio">
        <BooleanCell value={usage.includes("audio")} />
      </td>
      <td className="time">
        <BooleanCell value={usage.includes("time")} />
      </td>
    </tr>
  );
}

export function GenericParametersTable() {
  const { allOptions } = useCgiOptions();
  return (
    <table className="cgi-params table table-striped">
      <caption>CGI parameters</caption>
      <thead>
        <tr>
          <th className="parameter">Parameter</th>
          <th className="description">Description</th>
          <th className="manifest">Manifest</th>
          <th className="video">Video</th>
          <th className="audio">Audio</th>
          <th className="time">Time source</th>
        </tr>
      </thead>
      <tbody>
        {allOptions.value.map((opt) => (
          <GenericParametersRow key={opt.name} {...opt} />
        ))}
      </tbody>
    </table>
  );
}
