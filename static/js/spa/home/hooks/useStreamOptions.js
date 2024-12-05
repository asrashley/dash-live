import { useCallback } from "preact/hooks";
import { useComputed, useSignal } from "@preact/signals";

import { defaultCgiOptions, drmSystems } from "/libs/options.js";

const keyName = "dashlive.homepage.options";

function getDefaultOptions() {
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

const skipKeys = new RegExp(`^${[...drmSystems, 'drms', 'manifest', 'stream', 'mode'].join('|')}$`);
const manifestSkipKeys = /^player|dashjs|shaka/;

export function useStreamOptions({ streamNames, streamsMap }) {
  const data = useSignal(getDefaultOptions());
  const stream = useComputed(() => {
    const name = data.value.stream ?? streamNames.value[0];
    return streamsMap.value.get(name) ?? { title: "", value: "", mps: false };
  });
  const mode = useComputed(() => data.value.mode);
  const manifest = useComputed(() => data.value.manifest);
  const drms = useComputed(() => Object.fromEntries(drmSystems.map(name => [name, data.value[name] === "1"])));
  const nonDefaultOptions = useComputed(() => {
    const params = Object.entries(data.value)
      .filter(([key, value]) => defaultCgiOptions[key] != value)
      .filter(([key]) => !skipKeys.test(key));
    const drm = drmSystems.filter(system => data.value[system] === "1");
    if (drm.length) {
      params.push(['drm', drm.join(',')]);
    }
    return Object.fromEntries(params);
  });
  const manifestOptions = useComputed(() => Object.fromEntries(
    Object.entries(nonDefaultOptions.value).filter(key => !manifestSkipKeys.test(key))));

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

  return { data, drms, stream, mode, manifest, nonDefaultOptions, manifestOptions, setValue };
}
