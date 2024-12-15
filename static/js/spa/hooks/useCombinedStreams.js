import { createContext } from "preact";
import { useComputed } from "@preact/signals";

import { useAllStreams } from "./useAllStreams.js";
import { useAllMultiPeriodStreams } from "./useAllMultiPeriodStreams.js";

export const UseCombinedStreams = createContext(null);

export function useCombinedStreams() {
  const { allStreams: standardStreams, loaded: streamsLoaded, error: streamsError } = useAllStreams();
  const { streams: mpsStreams, loaded: mpsLoaded, error: mpsError } = useAllMultiPeriodStreams();
  const streamsMap = useComputed(() => {
    const smap = new Map();
    standardStreams.value.forEach((st) => {
      const { directory, title } = st;
      smap.set(`std.${directory}`, { title, value: directory, mps: false });
    });
    mpsStreams.value.forEach(({ name, title }) => {
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
  const loaded = useComputed(() => streamsLoaded && mpsLoaded);
  const error = useComputed(() => {
    if (!streamsError && !mpsError) {
      return null;
    }
    return [streamsError ?? '', mpsError ?? ''].join(' ');
  })
  return { streamNames, streamsMap, loaded, error };
}
