import { createContext } from "preact";
import { useContext, useEffect } from "preact/hooks";
import { type ReadonlySignal, useSignal } from "@preact/signals";

import { EndpointContext } from "../endpoints";
import { ContentRolesMap } from "../types/ContentRolesMap";

export interface UseContentRolesHook {
  contentRoles: ReadonlySignal<ContentRolesMap>;
  loaded: ReadonlySignal<boolean>;
  error: ReadonlySignal<string | null>;
}

export const ContentRolesContext = createContext<UseContentRolesHook>(null);

export function useContentRoles(): UseContentRolesHook {
  const apiRequests = useContext(EndpointContext);
  const contentRoles = useSignal<ContentRolesMap>({});
  const error = useSignal<string | null>(null);
  const loaded = useSignal<boolean>(false);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchContentRolesIfRequired = async () => {
      if (!loaded.value) {
        try {
          const data = await apiRequests.getContentRoles({
            signal,
          });
          if (!signal.aborted) {
            contentRoles.value = data;
            error.value = null;
            loaded.value = true;
          }
        } catch (err) {
          if (!signal.aborted) {
            error.value = `Failed to fetch content roles - ${err}`;
          }
        }
      }
    };

    fetchContentRolesIfRequired();

    return () => {
      if (!loaded.value) {
        controller.abort();
      }
    };
  }, [apiRequests, error, loaded, contentRoles]);

  return { contentRoles, error, loaded };
}
