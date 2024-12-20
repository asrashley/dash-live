import { createContext } from "preact";
import { useContext, useEffect } from "preact/hooks";
import { Signal, useSignal } from "@preact/signals";

import { EndpointContext } from "../endpoints";
import { ContentRolesMap } from "../types/ContentRolesMap";

export interface UseContentRolesHook {
  contentRoles: Signal<ContentRolesMap>;
  loaded: Signal<boolean>;
  error: Signal<string | null>;
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
          }
        } catch (err) {
          if (!signal.aborted) {
            console.error(err);
            error.value = `${err}`;
          }
        }
      }
    };
    fetchContentRolesIfRequired();

    return () => {
      controller.abort();
    };
  }, [apiRequests, error, loaded, contentRoles]);

  return { contentRoles, error, loaded };
}
