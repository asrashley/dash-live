import { createContext } from "preact";
import { useContext, useEffect } from "preact/hooks";
import { useSignal } from "@preact/signals";

import { EndpointContext } from "../endpoints.js";

export const AllManifestsContext = createContext();

export function useAllManifests() {
  const apiRequests = useContext(EndpointContext);
  const allManifests = useSignal();
  const error = useSignal(null);
  const names = useComputed(() => {
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
    fetchAllManifestsIfRequired({ allManifests, apiRequests, signal });

    return () => {
      controller.abort();
    };
  }, [apiRequests, allManifests, error]);

  return { allManifests, names, error };
}
