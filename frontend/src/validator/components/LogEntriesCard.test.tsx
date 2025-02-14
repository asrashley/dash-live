import { describe, expect, test } from "vitest";
import { signal } from "@preact/signals-core";

import { LogEntry } from "../types/LogEntry";
import { renderWithProviders } from "../../test/renderWithProviders";
import { LogEntriesCard } from "./LogEntriesCard";

describe("LogEntriesCard component", () => {
  const logItems: LogEntry[] = [
    {
      level: "info",
      text: "Prefetching media files required before validation can start",
      id: 1,
    },
    { level: "info", text: "Starting stream validation...", id: 2 },
    {
      level: "info",
      text: "Prefetching media files required before validation can start",
      id: 3,
    },
    { level: "info", text: "Validation complete after 11.0 seconds", id: 4 },
  ];
  const log = signal<LogEntry[]>([]);

  test("matches snapshot", () => {
    log.value = structuredClone(logItems);
    const { asFragment, getAllByText } = renderWithProviders(<LogEntriesCard log={log} />);
    logItems.forEach(({text}) => getAllByText(text));
    expect(asFragment()).toMatchSnapshot();
  });
});
