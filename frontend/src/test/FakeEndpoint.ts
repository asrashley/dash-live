import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFile } from 'node:fs/promises';
import fetchMock from '@fetch-mock/vitest';
import type { CallLog } from 'fetch-mock';
import log from 'loglevel';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export type ServerRouteProps = CallLog & {
    jsonParam?: object;
    routeParams?: RegExpExecArray["groups"];
    context: object;
    upk?: string;
};

export type HttpRequestHandlerResponse = ResponseInit & {
    body?: string | Buffer;
};

export type HttpRequestHandler = (props: ServerRouteProps) => Promise<HttpRequestHandlerResponse>;

export type HttpRequestModifier = (props: ServerRouteProps, response: HttpRequestHandlerResponse) => Promise<HttpRequestHandlerResponse>;

type PendingPromiseType = {
    resolve: (value: HttpRequestHandlerResponse) => void;
    reject: (reason?: unknown) => void;
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
        Object.values(this.pendingPromises).forEach(({reject}) => reject(new Error("shutdown")));
        this.pendingPromises = new Map();
    }

    setResponseModifier = (method: string, url: string, fn: HttpRequestModifier) => {
        const key = `${method.toLowerCase()}.${url}`;
        this.responseModifiers.set(key, fn);
    }

    addResponsePromise(method: string, url: string): Promise<HttpRequestHandlerResponse> {
        const key = `${method.toLowerCase()}.${url}`;
        return new Promise<HttpRequestHandlerResponse>((resolve, reject) => {
            log.trace(`responsePromise set "${key}"`);
            this.pendingPromises.set(key, { resolve, reject });
        });
    }

    setServerStatus(code: number | null) {
        this.serverStatus = code;
    }

    async fetchFixtureJson<T>(filename: string): Promise<T> {
        const text = await this.fetchFixtureText(filename);
        return JSON.parse(text) as T;
    }

    async fetchFixtureText(filename: string): Promise<string> {
        const fullName = path.join(__dirname, 'fixtures', filename);
        log.trace(`readFile "${fullName}"`);
        return await readFile(fullName, { encoding: 'utf-8' });
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
        const { url, options } = props;
        const { body, method } = options;
        const fullUrl = new URL(url, document.location.href);
        const key = `${method}.${fullUrl.pathname}`;

        log.trace(`routeHandler ${key}`);
        let result: HttpRequestHandlerResponse = notFound();
        const srp: ServerRouteProps = {
            ...props,
            context: {},
        };
        if (body) {
            srp.jsonParam = typeof body === 'string' ? JSON.parse(body as string) : body;
        }
        if (this.serverStatus !== null) {
            log.trace(`serverStatus: ${this.serverStatus}`);
            result = { status: this.serverStatus };
        } else {
            let handler: HttpRequestHandler | undefined = this.pathHandlers.get(key);
            if (handler === undefined) {
                log.trace(`check paramHandlers key="${key}"`);
                for (const rgx of this.paramHandlers.filter(ph => ph.method === method)) {
                    const match = rgx.re.exec(fullUrl.pathname);
                    if (match) {
                        log.trace(`Found handler "${rgx.re}"`);
                        srp.routeParams = match.groups;
                        handler = rgx.handler;
                        break;
                    }
                }
            }
            if (handler) {
                result = await handler(srp);
            } else {
                log.trace(`No handler found ${fullUrl.pathname}`);
            }
        }
        const modFn = this.responseModifiers.get(key);
        if (modFn) {
            result = await modFn(srp, result);
        }
        const pending = this.pendingPromises.get(key);
        if (pending) {
            log.trace(`resolve pending promise "${key}"`);
            this.pendingPromises.delete(key);
            pending.resolve(result);
        }
        return result;
    }
}

export function jsonResponse(payload: object | string, status: number = 200): HttpRequestHandlerResponse {
    const body = status !== 204 ? JSON.stringify(payload) : undefined;
    const contentLength = status !== 204 ? body.length : 0;
    return {
        body,
        status,
        headers: {
            'cache-control': 'max-age = 0, no_cache, no_store, must_revalidate',
            'content-type': 'application/json',
            'content-length': `${contentLength}`,
        },
    };
}

export function dataResponse(body: string, contentType: string, status: number = 200): HttpRequestHandlerResponse {
    const contentLength = status !== 204 ? body.length : 0;
    return {
        body,
        status,
        headers: {
            'content-type': contentType,
            'content-length': `${contentLength}`,
        },
    };
}

export function notFound(): HttpRequestHandlerResponse {
    return jsonResponse('', 404);
}
