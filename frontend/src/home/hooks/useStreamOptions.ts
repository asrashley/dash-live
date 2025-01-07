import { useCallback } from "preact/hooks";
import { type Signal, useComputed, useSignal } from "@preact/signals";

import { defaultCgiOptions, drmSystems } from "@dashlive/options";
import { CombinedStream } from "../../hooks/useCombinedStreams";

const keyName = "dashlive.homepage.options";

function getDefaultOptions(): object {
  const lsKey = localStorage.getItem(keyName);
  const previousOptions = lsKey ? JSON.parse(lsKey) : {};
  return {
    ...defaultCgiOptions,
    manifest: "hand_made.mpd",
    mode: "vod",
    stream: undefined,
    ...previousOptions,
  };
}

const skipKeys = new RegExp(`^(${[
  ...drmSystems,
  ...drmSystems.map(name => `${name}__enabled`),
  ...drmSystems.map(name => `${name}__drmloc`),
  'drms', 'manifest', 'stream', 'mode'].join('|')})$`);
const manifestSkipKeys = /^(player|dashjs|shaka)/;

export type EnabledDrmSystems = {
  [name: string]: boolean;
};

export interface UseStreamOptionsHook {
  data: Signal<object>;
  drms: Signal<EnabledDrmSystems>;
  stream: Signal<CombinedStream>;
  mode: Signal<string>;
  manifest: Signal<string>;
  nonDefaultOptions: Signal<object>;
  manifestOptions: Signal<object>;
  setValue: (name: string, value: string | number | boolean) => void;
  resetAllValues: () => void;
}

const emptyStream: CombinedStream ={
  title: "",
  value: "",
  mps: false
}

export interface UseStreamOptionsProps {
  streamNames: Signal<string[]>;
  streamsMap: Signal<Map<string, CombinedStream>>;
}
export function useStreamOptions({ streamNames, streamsMap }: UseStreamOptionsProps): UseStreamOptionsHook {
  const data = useSignal<object>(getDefaultOptions());
  const stream = useComputed<CombinedStream>(() => {
    const name: string = data.value['stream'] ?? streamNames.value[0];
    return streamsMap.value.get(name) ?? emptyStream;
  });
  const mode = useComputed<string>(() => data.value['mode']);
  const manifest = useComputed<string>(() => data.value['manifest']);
  const drms = useComputed<EnabledDrmSystems>(() => Object.fromEntries(drmSystems.map(name => [name, data.value[name] === "1"])));
  const nonDefaultOptions = useComputed<object>(() => {
    const params = Object.entries(data.value)
      .filter(([key, value]) => defaultCgiOptions[key] != value)
      .filter(([key]) => !skipKeys.test(key));
    const drm = drmSystems.filter(system => data.value[system] === "1").map(system => {
      const drmLoc = data.value[`${system}__drmloc`];
      return drmLoc ? `${system}-${drmLoc}`: system;
    });
    if (drm.length) {
      params.push(['drm', drm.join(',')]);
    }
    return Object.fromEntries(params);
  });
  const manifestOptions = useComputed<object>(() => Object.fromEntries(
    Object.entries(nonDefaultOptions.value).filter(([key]) => !manifestSkipKeys.test(key))));

  const setValue = useCallback(
    (name, value) => {
      if (value === true) {
        value = "1";
      } else if (value === false) {
        value = "0";
      }
      data.value = {
        ...data.value,
        [name]: value,
      };
      if (name === "stream" && mode.value === "odvod") {
        const nextStream = streamsMap.value.get(value);
        if (nextStream?.mps) {
          data.value = {
            ...data.value,
            mode: "vod",
          };
        }
      }
      const params = Object.fromEntries(
        Object.entries(data.value).filter(
          ([key, value]) => defaultCgiOptions[key] !== value
        )
      );
      localStorage.setItem(keyName, JSON.stringify(params));
    },
    [data, mode, streamsMap]
  );

  const resetAllValues = useCallback(() => {
    data.value = { ...getDefaultOptions() };
    localStorage.removeItem(keyName);
  }, [data]);

  return { data, drms, stream, mode, manifest, nonDefaultOptions, manifestOptions, setValue, resetAllValues };
}
