import { createContext } from "preact";
import { Signal, useComputed } from "@preact/signals";

import { useAllStreams } from "./useAllStreams";
import { useAllMultiPeriodStreams } from "./useAllMultiPeriodStreams";

export type CombinedStream = {
  title: string;
  value: string;
  mps: boolean;
};

export interface UseCombinedStreamsHook {
  streamNames: Signal<string[]>;
  streamsMap: Signal<Map<string, CombinedStream>>;
  loaded: Signal<boolean>;
  error: Signal<string | null>;
}

export const UseCombinedStreams = createContext(null);

export function useCombinedStreams(): UseCombinedStreamsHook {
  const { allStreams: standardStreams, loaded: streamsLoaded, error: streamsError } = useAllStreams();
  const { streams: mpsStreams, loaded: mpsLoaded, error: mpsError } = useAllMultiPeriodStreams();
  const streamsMap = useComputed<Map<string, CombinedStream>>(() => {
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
  const streamNames = useComputed<string[]>(() => {
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
  const loaded = useComputed<boolean>(() => streamsLoaded.value && mpsLoaded.value);
  const error = useComputed<string | null>(() => {
    if (!streamsError && !mpsError) {
      return null;
    }
    return [streamsError ?? '', mpsError ?? ''].join(' ');
  })
  return { streamNames, streamsMap, loaded, error };
}
