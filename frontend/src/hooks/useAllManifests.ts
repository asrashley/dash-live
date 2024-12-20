import { createContext } from "preact";
import { useContext, useEffect } from "preact/hooks";
import { Signal, useComputed, useSignal } from "@preact/signals";

import { EndpointContext } from "../endpoints";
import { AllManifests } from "../types/AllManifests";


export interface UseAllManifestsHooks {
  allManifests: Signal<AllManifests | undefined>;
  names: Signal<string[]>;
  error: Signal<string | null>;
}

export const AllManifestsContext = createContext<UseAllManifestsHooks>(null);

export function useAllManifests(): UseAllManifestsHooks {
  const apiRequests = useContext(EndpointContext);
  const allManifests = useSignal<AllManifests | undefined>();
  const error = useSignal<string | null>(null);
  const names = useComputed<string[]>(() => {
    const keys = allManifests.value ? [...Object.keys(allManifests.value)]: [];
    keys.sort();
    return keys;
  });

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchAllManifestsIfRequired = async () => {
      if (!allManifests.value) {
        try {
          const data = await apiRequests.getAllManifests({
            signal,
          });
          if (!signal.aborted) {
            allManifests.value = data;
            error.value = null;
          }
        } catch (err) {
          if (!signal.aborted) {
            console.error(err);
            error.value = `${err}`;
          }
        }
      }
    };
    fetchAllManifestsIfRequired();

    return () => {
      controller.abort();
    };
  }, [apiRequests, allManifests, error]);

  return { allManifests, names, error };
}
