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
  const currentTime = signal<number>(0);

  test("matches snapshot", () => {
    currentTime.value = 83;
    events.value = [...exampleEvents];
    const { asFragment, getBySelector } = renderWithProviders(
      <StatusPanel events={events} currentTime={currentTime} />
    );
    const tcElt = getBySelector(".play-position") as HTMLDivElement;
    expect(tcElt?.innerHTML).toEqual("00:01:23");
    expect(asFragment()).toMatchSnapshot();
  });
});
