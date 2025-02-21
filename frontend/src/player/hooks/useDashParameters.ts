import { useCallback, useContext } from "preact/hooks";
import { useComputed, type ReadonlySignal } from "@preact/signals";

import { EndpointContext } from "../../endpoints";
import { useJsonRequest, UseJsonRequestHook } from "../../hooks/useJsonRequest";
import { DashParameters } from "../types/DashParameters";
import { KeyParameters } from "../types/KeyParameters";

interface UseDashParametersHook {
    dashParams: ReadonlySignal<DashParameters | undefined>;
    keys: ReadonlySignal<Map<string, KeyParameters>>;
    error: UseJsonRequestHook<DashParameters | undefined>['error'];
    loaded: UseJsonRequestHook<DashParameters | undefined>['loaded'];
}

export function useDashParameters(mode: string, stream: string, manifest: string, params: Readonly<URLSearchParams>): UseDashParametersHook {
    const apiRequests = useContext(EndpointContext);
    const request = useCallback((signal: AbortSignal) => apiRequests.getDashParameters(mode, stream, manifest, params,
        {
            signal,
        }), [apiRequests, manifest, mode, params, stream]);
    const { data: dashParams, loaded, error } = useJsonRequest<DashParameters | undefined>({
        request,
        initialData: undefined,
        name: 'dash parameters',
    });
    const keys = useComputed(() => {
        const rv = new Map();
        if (!dashParams.value?.dash) {
            return rv;
        }
        const { dash } = dashParams.value;
        for (const period of dash.periods) {
            for (const adaptation of period.adaptationSets) {
                for (const [kid, keypair] of Object.entries(adaptation.keys ?? {})) {
                    rv.set(kid, keypair);
                }
            }
        }
        return rv;
    });

    return { dashParams, keys, error, loaded };
}