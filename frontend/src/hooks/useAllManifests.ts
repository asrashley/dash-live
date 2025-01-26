import { createContext } from "preact";
import { useCallback, useContext } from "preact/hooks";
import { Signal, useComputed } from "@preact/signals";

import { EndpointContext } from "../endpoints";
import { AllManifests } from "../types/AllManifests";
import { useJsonRequest } from "./useJsonRequest";

export interface UseAllManifestsHooks {
  allManifests: Signal<AllManifests | undefined>;
  names: Signal<string[]>;
  error: Signal<string | null>;
}

export const AllManifestsContext = createContext<UseAllManifestsHooks>(null);

export function useAllManifests(): UseAllManifestsHooks {
  const apiRequests = useContext(EndpointContext);
  const request = useCallback((signal: AbortSignal) => apiRequests.getAllManifests({
      signal,
    }), [apiRequests]);
  const {data: allManifests, error } = useJsonRequest<AllManifests | undefined>({
    request,
    initialData: undefined,
    name: 'all manifests',
  });
  const names = useComputed<string[]>(() => {
    const keys = allManifests.value ? [...Object.keys(allManifests.value)]: [];
    keys.sort();
    return keys;
  });

  return { allManifests, names, error };
}
