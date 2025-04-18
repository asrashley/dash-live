import { useCallback } from "preact/hooks";
import { type ReadonlySignal, useComputed } from "@preact/signals";

import { defaultCgiOptions, drmSystems } from "@dashlive/options";
import { CombinedStream } from "../../hooks/useCombinedStreams";
import { InputFormData } from "../../form/types/InputFormData";
import { FormGroupsProps } from "../../form/types/FormGroupsProps";
import { useLocalStorage } from "../../hooks/useLocalStorage";

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
  data: FormGroupsProps['data'];
  disabledFields: FormGroupsProps['disabledFields'];
  drms: ReadonlySignal<EnabledDrmSystems>;
  stream: ReadonlySignal<CombinedStream>;
  mode: ReadonlySignal<string>;
  manifest: ReadonlySignal<string>;
  nonDefaultOptions: ReadonlySignal<object>;
  manifestOptions: ReadonlySignal<object>;
  setValue: (name: string, value: string | number | boolean) => void;
  resetAllValues: () => void;
}

const emptyStream: CombinedStream = {
  title: "",
  value: "",
  mps: false
}

export interface UseStreamOptionsProps {
  streamNames: ReadonlySignal<string[]>;
  streamsMap: ReadonlySignal<Map<string, CombinedStream>>;
}
export function useStreamOptions({ streamNames, streamsMap }: UseStreamOptionsProps): UseStreamOptionsHook {
  const { dashOptions: data, setDashOption, resetDashOptions } = useLocalStorage();
  const stream = useComputed<CombinedStream>(() => {
    const name: string = (data.value['stream'] as string | undefined) ?? streamNames.value[0];
    return streamsMap.value.get(name) ?? emptyStream;
  });
  const mode = useComputed<string>(() => data.value['mode'] as string);
  const manifest = useComputed<string>(() => data.value['manifest'] as string);
  const drms = useComputed<EnabledDrmSystems>(() => Object.fromEntries(drmSystems.map(name => [name, data.value[name] === "1"])));
  const nonDefaultOptions = useComputed<InputFormData>(() => {
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
  const manifestOptions = useComputed<InputFormData>(() => Object.fromEntries(
    Object.entries(nonDefaultOptions.value).filter(([key]) => !manifestSkipKeys.test(key))));
  const disabledFields = useComputed<Record<string, boolean>>(() => {
    const disabled: Record<string, boolean> = {
      mode__odvod: stream.value.mps,
    };
    return disabled;
  });

  const setValue = useCallback(
    (name: string, value: string | number | boolean) => {
      setDashOption(name, value);
      if (name === "stream" && mode.value === "odvod") {
        const nextStream = streamsMap.value.get(value as string);
        if (nextStream?.mps) {
          setDashOption("mode", "vod");
        }
      }
    },
    [mode, setDashOption, streamsMap]
  );

  return {
    data,
    disabledFields,
    drms,
    stream,
    mode,
    manifest,
    nonDefaultOptions,
    manifestOptions,
    setValue,
    resetAllValues: resetDashOptions,
  };
}
