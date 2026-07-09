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

export const UseCombinedStreams = createContext<UseCombinedStreamsHook>(null!);

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
    const names: string[] = [...smap.keys()];
    names.sort((a: string, b: string) => {
      const streamA = smap.get(a);
      const streamB = smap.get(b);
      const t1 = streamA?.title ?? '';
      const t2 = streamB?.title ?? '';
      return t1.localeCompare(t2);
    });
    return names;
  });
  const loaded = useComputed<boolean>(() => streamsLoaded.value && mpsLoaded.value);
  const error = useComputed<string | null>(() => {
    if (!streamsError.value && !mpsError.value) {
      return null;
    }
    const errors: string[] = [];
    if (streamsError.value) {
      errors.push(streamsError.value);
    }
    if (mpsError.value) {
      errors.push(mpsError.value);
    }
    return errors.join(', ');
  });
  return { streamNames, streamsMap, loaded, error };
}
