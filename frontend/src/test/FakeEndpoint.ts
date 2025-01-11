import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFile } from 'node:fs/promises';
import fetchMock from '@fetch-mock/vitest';
import type { CallLog, RouteResponse } from 'fetch-mock';
import log from 'loglevel';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export type ServerRouteProps = CallLog & {
    jsonParam?: object;
    routeParams?: RegExpExecArray["groups"];
    context: object;
};

export type HttpRequestHandler = (props: ServerRouteProps) => RouteResponse;

export type HttpRequestModifier = (props: ServerRouteProps, response: RouteResponse) => Promise<RouteResponse>;

type PendingPromiseType = {
    resolve: (value: RouteResponse) => void;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    reject: (reason?: any) => void;
};

type ParamHandler = {
    re: RegExp;
    method: string;
    handler: HttpRequestHandler;
};
export class FakeEndpoint {
    private isShutdown: boolean = false;
    private serverStatus: number | null = null;
    private responseModifiers: Map<string, HttpRequestModifier> = new Map();
    private pendingPromises: Map<string, PendingPromiseType> = new Map();
    private pathHandlers: Map<string, HttpRequestHandler> = new Map();
    private paramHandlers: ParamHandler[] = [];

    constructor(private origin: string) {
        log.trace(`FakeEndpoint "begin:${origin}/"`);
        fetchMock.route(`begin:${origin}/`, this.routeHandler);
    }

    get(path: RegExp | string, handler: HttpRequestHandler): FakeEndpoint {
        this.setHandler('get', path, handler);
        return this;
    }

    post(path: RegExp | string, handler: HttpRequestHandler): FakeEndpoint {
        this.setHandler('post', path, handler);
        return this;
    }

    put(path: RegExp | string, handler: HttpRequestHandler): FakeEndpoint {
        this.setHandler('put', path, handler);
        return this;
    }

    delete(path: RegExp | string, handler: HttpRequestHandler): FakeEndpoint {
        this.setHandler('delete', path, handler);
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

    private setHandler(method: string, path: RegExp | string, handler: HttpRequestHandler) {
        if (typeof path === "string") {
            const key = `${method}.${path}`;
            this.pathHandlers.set(key, handler);
        }
        else {
            this.paramHandlers.push({
                handler,
                method,
                re: path as RegExp,
            });
        }
    }

    private routeHandler = async (props: CallLog) => {
        const {url, options} = props;
        const { body, method } = options;
        const fullUrl = new URL(url, document.location.href);
        const key = `${method}.${fullUrl.pathname}`;

        log.trace(`routeHandler ${key}`);
        if (this.serverStatus !== null) {
            return this.serverStatus;
        }
        let handler: HttpRequestHandler | undefined = this.pathHandlers.get(key);
        let match: RegExpExecArray | null = null;
        if (handler === undefined) {
            log.debug(`check paramHandlers ${key}`);
            for (const rgx of this.paramHandlers.filter(ph => ph.method === method)) {
                match = rgx.re.exec(fullUrl.pathname);
                if (match) {
                    handler = rgx.handler;
                    break;
                }
            }
        }
        if (!handler) {
            log.trace(`No handler found ${fullUrl.pathname}`);
            return notFound();
        }
        const srp: ServerRouteProps = {
            ...props,
            context: {},
        };
        if (match) {
            srp.routeParams = match.groups;
        }
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

export function notFound(): RouteResponse {
    return jsonResponse('', 404);
}
