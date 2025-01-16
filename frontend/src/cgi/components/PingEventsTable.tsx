import { EventExtraField, EventsTable } from "./EventsTable";

const extraFields: EventExtraField[] = [
  {
    name: "ping_value",
    defaultValue: "0",
    description:
      "The value attribute to use for this event stream. The value field is used with the schemeIdUri to uniquely identify an event stream",
  },
  {
    name: "ping_version",
    defaultValue: 0,
    description: "Version of emsg syntax to use for inband events",
  },
];

export function PingEventsTable() {
  return (
    <EventsTable
      name="ping"
      description="PING event parameters (urn:dash-live:pingpong:2022"
      extras={extraFields}
    />
  );
}
