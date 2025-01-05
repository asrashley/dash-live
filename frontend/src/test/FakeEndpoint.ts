import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFile } from 'node:fs/promises';
import fetchMock from '@fetch-mock/vitest';
import type { CallLog, RouteResponse } from 'fetch-mock';
import log from 'loglevel';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export type ServerRouteProps = CallLog & {
    notFound: () => RouteResponse;
    jsonParam?: object;
    context: object;
}

export type HttpRequestHandler = (props: ServerRouteProps) => RouteResponse;

export type HttpRequestModifier = (props: ServerRouteProps, response: RouteResponse) => Promise<RouteResponse>;

type PendingPromiseType = {
    resolve: (value: RouteResponse) => void;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    reject: (reason?: any) => void;
};

export class FakeEndpoint {
    private isShutdown: boolean = false;
    private serverStatus: number | null = null;
    private responseModifiers: Map<string, HttpRequestModifier> = new Map();
    private pendingPromises: Map<string, PendingPromiseType> = new Map();
    private handlers: Map<string, HttpRequestHandler> = new Map();

    constructor(private origin: string) {
        log.trace(`FakeEndpoint "begin:${origin}/"`);
        fetchMock.route(`begin:${origin}/`, this.routeHandler);
    }

    get(path: string, handler: HttpRequestHandler): FakeEndpoint {
        this.setHandler('get', path, handler);
        return this;
    }

    put(path: string, handler: HttpRequestHandler): FakeEndpoint {
        this.setHandler('put', path, handler);
        return this;
    }

    shutdown() {
        this.isShutdown = true;
        this.serverStatus = 503;
        for (const [url, { reject }] of Object.entries(this.pendingPromises)) {
            reject(new Error(url));
        }
        this.pendingPromises = new Map();
    }

    setResponseModifier = (method: string, url: string, fn: HttpRequestModifier) => {
        const key = `${method.toLowerCase()}.${url}`;
        this.responseModifiers.set(key, fn);
    }

    addResponsePromise(method: string, url: string): Promise<RouteResponse> {
        const key = `${method.toLowerCase()}.${url}`;
        return new Promise<RouteResponse>((resolve, reject) => {
            this.pendingPromises.set(key, { resolve, reject });
        });
    }

    setServerStatus(code: number | null) {
        this.serverStatus = code;
    }

    async fetchFixtureJson<T>(filename: string): Promise<T> {
        const text = await readFile(path.join(__dirname, 'fixtures', filename), { encoding: 'utf-8'});
        return JSON.parse(text) as T;
    }

    private setHandler(method: string, path: string, handler: HttpRequestHandler) {
        const key = `${method}.${path}`;
        log.trace(`setHandler ${method} ${path} key="${key}"`);
        this.handlers.set(key, handler);
    }

    private routeHandler = async (props: CallLog) => {
        const {url, options} = props;
        const { body, method } = options;
        const fullUrl = new URL(url, document.location.href);
        const key = `${method}.${fullUrl.pathname}`;
        log.trace(`routeHandler key="${key}"`);
        if (this.serverStatus !== null) {
            log.trace(`serverStatus=${this.serverStatus}`);
            return this.serverStatus;
        }
        const handler = this.handlers.get(key);
        if (!handler) {
            log.trace(`url=${fullUrl} not found`);
            return 404;
        }
        const srp: ServerRouteProps = {
            ...props,
            context: {},
            notFound: () => {
                return jsonResponse('', 404);
            }
        };
        if (body) {
            srp.jsonParam = typeof body === 'string' ? JSON.parse(body as string) : body;
        }
        let result = await handler(srp);
        const modFn = this.responseModifiers.get(key);
        if (modFn) {
            result = await modFn(srp, result);
        }
        if (this.serverStatus !== null) {
            return this.serverStatus;
        }
        const pending = this.pendingPromises.get(key);
        if (pending) {
            this.pendingPromises.delete(key);
            pending.resolve(result);
        }
        return result;
    }
}

/*
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function isPromise(item: any): boolean {
    return (typeof item === 'object' && typeof item?.then === 'function' && typeof item?.catch === 'function');
}
*/

export function jsonResponse(payload: object | string, status: number = 200): RouteResponse {
    const body = status !== 204 ? JSON.stringify(payload) : undefined;
    const contentLength = status !== 204 ? body.length : 0;
    return {
        body,
        status,
        headers: {
            'Cache-Control': 'max-age = 0, no_cache, no_store, must_revalidate',
            'Content-Type': 'application/json',
            'Content-Length': contentLength,
        },
    };
}




