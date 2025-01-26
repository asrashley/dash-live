import { createContext } from "preact";
import { useCallback, useContext } from "preact/hooks";
import { type ReadonlySignal } from "@preact/signals";

import { EndpointContext } from "../endpoints";
import { ContentRolesMap } from "../types/ContentRolesMap";
import { useJsonRequest } from "./useJsonRequest";

export interface UseContentRolesHook {
  contentRoles: ReadonlySignal<ContentRolesMap>;
  loaded: ReadonlySignal<boolean>;
  error: ReadonlySignal<string | null>;
}

export const ContentRolesContext = createContext<UseContentRolesHook>(null);

export function useContentRoles(): UseContentRolesHook {
  const apiRequests = useContext(EndpointContext);
  const request = useCallback((signal: AbortSignal) => apiRequests.getContentRoles({
    signal,
  }), [apiRequests]);
  const { data: contentRoles, error, loaded } = useJsonRequest<ContentRolesMap>({
    request,
    initialData: {},
    name: 'content roles',
  });

  return { contentRoles, error, loaded };
}
