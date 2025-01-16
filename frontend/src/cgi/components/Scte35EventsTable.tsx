import { EventExtraField, EventsTable } from "./EventsTable";

const extraFields: EventExtraField[] = [
  {
    name: "scte35_value",
    defaultValue: "0",
    description:
      "The value attribute to use for this event stream. The value field is used with the schemeIdUri to uniquely identify an event stream",
  },
];

export function Scte35EventsTable() {
  return (
    <EventsTable
      name="scte35"
      description="SCTE35 event parameters (urn:scte:scte35:2014:xml+bin)"
      extras={extraFields}
    />
  );
}
