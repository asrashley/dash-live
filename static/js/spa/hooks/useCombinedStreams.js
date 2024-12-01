import { createContext } from "preact";
import { useComputed } from "@preact/signals";

import { useAllStreams } from "./useAllStreams.js";
import { useAllMultiPeriodStreams } from "./useAllMultiPeriodStreams.js";

export const UseCombinedStreams = createContext(null);

export function useCombinedStreams() {
  const { allStreams: allStandardStreams } = useAllStreams();
  const { streams: allMpsStreams } = useAllMultiPeriodStreams();
  const streamsMap = useComputed(() => {
    const smap = new Map();
    allStandardStreams.value.forEach((st) => {
      const { directory, title } = st;
      smap.set(`std.${directory}`, { title, value: directory, mps: false });
    });
    allMpsStreams.value.forEach(({ name, title }) => {
      smap.set(`mps.${name}`, { title, value: name, mps: true });
    });
    return smap;
  });
  const streamNames = useComputed(() => {
    const smap = streamsMap.value;
    const names = [...smap.keys()];
    names.sort((a, b) => {
      const t1 = smap.get(a).title;
      const t2 = smap.get(b).title;
      if (t1 == t2) {
        return 0;
      }
      if (t1 < t2) {
        return -1;
      }
      return 1;
    });
    return names;
  });
  return { streamNames, streamsMap };
}
