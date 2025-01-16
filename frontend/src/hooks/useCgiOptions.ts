import { useContext, useEffect } from "preact/hooks";
import { type ReadonlySignal, useSignal } from "@preact/signals";

import { EndpointContext } from "../endpoints";
import { CgiOptionDescription } from "../types/CgiOptionDescription";

export interface UseCgiOptionsHook {
  allOptions: ReadonlySignal<CgiOptionDescription[]>;
  loaded: ReadonlySignal<boolean>;
  error: ReadonlySignal<string | null>;
}

export function useCgiOptions(): UseCgiOptionsHook {
  const apiRequests = useContext(EndpointContext);
  const allOptions = useSignal<CgiOptionDescription[]>([]);
  const error = useSignal<string | null>(null);
  const loaded = useSignal<boolean>(false);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchCgiOptionsIfRequired = async () => {
      if (!loaded.value) {
        try {
          const data = await apiRequests.getCgiOptions({
            signal,
          });
          if (!signal.aborted) {
            allOptions.value = data;
            error.value = null;
            loaded.value = true;
          }
        } catch (err) {
          if (!signal.aborted) {
            error.value = `Failed to fetch CGI options - ${err}`;
          }
        }
      }
    };

    fetchCgiOptionsIfRequired();

    return () => {
      if (!loaded.value) {
        controller.abort();
      }
    };
  }, [apiRequests, error, loaded, allOptions]);

  return { allOptions, error, loaded };
}
