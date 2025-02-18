import { useContext } from "preact/hooks";
import { type ReadonlySignal, useComputed } from "@preact/signals";

import { fieldGroups, drmSystems } from '@dashlive/options';

import { useAllManifests  } from '../../hooks/useAllManifests';
import { UseCombinedStreams  } from '../../hooks/useCombinedStreams';
import { StaticInputProps } from "../../form/types/StaticInputProps";
import { InputFormGroup } from "../../form/types/InputFormGroup";

const drmSkipNames = new RegExp(`^${drmSystems.map(name => `${name}__enabled`).join('|')}$`);

interface UseFieldGroupsHook {
  homeFieldGroups: ReadonlySignal<InputFormGroup[]>;
}

export function useFieldGroups(): UseFieldGroupsHook {
  const { allManifests, names } = useAllManifests();
  const { streamNames, streamsMap } = useContext(UseCombinedStreams);

  const homeFieldGroups = useComputed<InputFormGroup[]>(() => {
    const playbackMode: StaticInputProps = {
      name: "mode",
      shortName: "mode",
      fullName: "playbackMode",
      title: "Playback Mode",
      type: "radio",
      options: [
        {
          title: "Video On Demand (using live profile)",
          value: "vod",
        },
        {
          title: "Live stream (using live profile)",
          value: "live",
        },
        {
          title: "Video On Demand (using on-demand profile)",
          value: "odvod",
        },
      ],
    };
    const selectManifest: StaticInputProps = {
      name: "manifest",
      shortName: "manifest",
      fullName: "manifest",
      title: "Manifest",
      text: "Manifest template to use",
      type: "select",
      options: names.value.map((name: string) => {
        const msft = allManifests.value[name];
        return {
          title: msft.title,
          value: name,
        };
      }),
    };
    const selectStream: StaticInputProps = {
      name: "stream",
      shortName: "stream",
      fullName: "stream",
      title: "Stream",
      text: "Stream to play",
      type: "select",
      options: streamNames.value.map((value: string) => ({
        title: streamsMap.value.get(value).title,
        value,
      })),
    };
    const selectDrmSystem: StaticInputProps = {
      name: "drms",
      shortName: "drms",
      fullName: "drms",
      title: "DRM systems",
      text: "DRM systems to enable for encrypted AdaptationSets",
      type: "multiselect",
      options: drmSystems.map((name: string) => ({
        name,
        title: name,
        value: name,
      })),
    };
    const generalOptions: InputFormGroup = {
      ...fieldGroups[0],
      fields: [
        playbackMode,
        selectManifest,
        selectStream,
        selectDrmSystem,
        ...fieldGroups[0].fields,
      ],
    };
    const otherGroups: InputFormGroup[] = fieldGroups.slice(1).map(grp => ({
        ...grp,
        fields: grp.fields.filter(({name}) => !drmSkipNames.test(name)),
    }));
    return [generalOptions, ...otherGroups];
  });

  return { homeFieldGroups };
}
