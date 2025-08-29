import { signal } from "@preact/signals";
import { describe, expect, test } from "vitest";
import { renderWithProviders } from "../../test/renderWithProviders";
import { StatusPanel } from "./StatusPanel";
import { StatusEvent } from "../types/StatusEvent";

describe("StatusPanel", () => {
  const exampleEvents: StatusEvent[] = [
    {
      id: 1,
      position: 0.25,
      timecode: "00:00:00.250",
      event: "loadedmetadata",
      text: "",
    },
    {
      id: 2,
      position: 1,
      timecode: "00:00:01.000",
      event: "canplay",
      text: "",
    },
    {
      id: 3,
      position: 1.5,
      timecode: "00:00:01.500",
      event: "playing",
      text: "",
    },
  ];
  const events = signal<StatusEvent[]>([]);

  test("matches snapshot", () => {
    events.value = [...exampleEvents];
    const { asFragment, getByText } = renderWithProviders(
      <StatusPanel events={events} />
    );
    events.value.forEach(({timecode}) => {
      getByText(timecode);
    });
    expect(asFragment()).toMatchSnapshot();
  });
});
