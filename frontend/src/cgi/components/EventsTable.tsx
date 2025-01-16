export interface EventExtraField {
  name: string;
  defaultValue: string | number;
  description: string;
}

function ExtraFieldRow({ name, defaultValue, description }: EventExtraField) {
  return (
    <tr>
      <td>{name}</td>
      <td>{defaultValue}</td>
      <td className="description">{description}</td>
    </tr>
  );
}

export interface EventsTableProps {
  name: string;
  description: string;
  extras: EventExtraField[];
}
export function EventsTable({ name, description, extras }: EventsTableProps) {
  return (
    <table className="table table-striped event-parameters">
      <caption>
        <a id={name}>{description}</a>
      </caption>
      <thead>
        <tr>
          <th>Parameter</th>
          <th>Default</th>
          <th class="description">Description</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>{name}_count</td>
          <td>0</td>
          <td className="description">Number of events to insert</td>
        </tr>
        <tr>
          <td>{name}_duration</td>
          <td>200</td>
          <td className="description">Duration of each event</td>
        </tr>
        <tr>
          <td>{name}_inband</td>
          <td>1</td>
          <td className="description">
            In-manifest (0) or inband with the media (1)
          </td>
        </tr>
        <tr>
          <td>{name}_interval</td>
          <td>1000</td>
          <td className="description">
            Time period between events (timescale units)
          </td>
        </tr>
        <tr>
          <td>{name}_start</td>
          <td>0</td>
          <td className="description">Time of first event (timescale units)</td>
        </tr>
        <tr>
          <td>{name}_timescale</td>
          <td>100</td>
          <td className="description">Timescale (ticks per second)</td>
        </tr>
        {extras.map((ext) => (
          <ExtraFieldRow key={ext.name} {...ext} />
        ))}
      </tbody>
    </table>
  );
}
