import { useContext } from "preact/hooks";
import { useComputed } from "@preact/signals";

import { fieldGroups, drmSystems } from "/libs/options.js";
import { useAllManifests, UseCombinedStreams  } from "@dashlive/hooks";
import { StreamOptionsContext } from '../types/StreamOptionsHook.js';

export function useFieldGroups() {
  const { allManifests, names } = useAllManifests();
  const { streamNames, streamsMap } = useContext(UseCombinedStreams);
  const { stream, manifest, mode, drms } = useContext(StreamOptionsContext);

  const homeFieldGroups = useComputed(() => {
    const playbackMode = {
      name: "mode",
      title: "Playback Mode",
      type: "radio",
      options: [
        {
          title: "Video On Demand (using live profile)",
          value: "vod",
          selected: mode.value === "vod",
        },
        {
          title: "Live stream (using live profile)",
          value: "live",
          selected: mode.value === "live",
        },
        {
          title: "Video On Demand (using on-demand profile)",
          value: "odvod",
          selected: mode.value === "odvod",
          disabled: stream.value.mps,
        },
      ],
    };
    const selectManifest = {
      name: "manifest",
      title: "Manifest",
      text: "Manifest template to use",
      type: "select",
      options: names.value.map((name) => {
        const msft = allManifests.value[name];
        return {
          title: msft.title,
          value: name,
          selected: name === manifest.value,
        };
      }),
      value: manifest.value,
    };
    const selectStream = {
      name: "stream",
      title: "Stream",
      text: "Stream to play",
      type: "select",
      options: streamNames.value.map((value) => ({
        title: streamsMap.value.get(value).title,
        value,
        selected: value === stream.value,
      })),
      value: stream.value,
    };
    const selectDrmSystem = {
      name: "drms",
      title: "DRM systems",
      text: "DRM systems to enable for encrypted AdaptationSets",
      type: "multiselect",
      options: drmSystems .map(name => ({
        name,
        title: name,
        checked: !!drms.value[name],
      })),
    };
    const generalOptions = {
      ...fieldGroups[0],
      fields: [
        playbackMode,
        selectManifest,
        selectStream,
        selectDrmSystem,
        ...fieldGroups[0].fields,
      ],
    };
    return [generalOptions, ...fieldGroups.slice(1)];
  });

  return { homeFieldGroups };
}
