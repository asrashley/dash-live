import { Socket } from 'socket.io-client';
import log from 'loglevel';

import { InstallStreamCommand, ValidatorFinishedEvent, ValidatorProgressEvent } from "../validator/hooks/useValidatorWebsocket";
import { ValidatorSettings } from "../validator/types/ValidatorSettings";
import { LogEntry } from '../validator/types/LogEntry';
import { ManifestEvent } from '../validator/types/ManifestEvent';
import { FakeEndpoint } from './FakeEndpoint';
import { ErrorEntry } from '../validator/types/ErrorEntry';
import { exampleCodecs } from './fixtures/exampleCodecs';
import { checkValidatorSettings } from '../validator/utils/checkValidatorSettings';

export type WebsocketEventListener = (...args: unknown[]) => void;

type ServerCommand = {
    method: string;
}

type ServerEventName = 'codecs' | 'finished' | 'install' | 'log' | 'manifest' | 'manifest-errors';
type ServerEventPayload = string[] | ValidatorFinishedEvent | InstallStreamCommand | Omit<LogEntry, 'id'> | ManifestEvent | ErrorEntry[];

type GenerateServerEvent = (pct: number) => Promise<[ServerEventName, ServerEventPayload]>;

type PendingServerEvent = {
    pct: number;
    generate: GenerateServerEvent;
};

export class MockWebsocketServer {
    private listeners = new Map<string, WebsocketEventListener>();
    private settings?: ValidatorSettings;
    private progress: ValidatorProgressEvent = {
        pct: 0,
        text: '',
        aborted: false,
        finished: false,
    };
    private pending: PendingServerEvent[] = [];
    private pendingCommands: Promise<void>[] = [];
    private manifestErrors: ErrorEntry[] = [];
    private donePromise?: PromiseWithResolvers<void>;

    // eslint-disable-next-line no-useless-constructor
    constructor(
        private sock: Socket,
        private endpoint: FakeEndpoint
    ) {
        log.debug(`MockWebsocketServer(${endpoint.getOrigin()})`)
    }

    async destroy() {
        this.listeners = new Map();
        this.settings = undefined;
        this.donePromise?.reject(new Error('destroy'));
        this.donePromise = undefined;
        const { pendingCommands } = this;
        this.pendingCommands = [];
        await Promise.all(pendingCommands);
        this.pending = [];
        this.manifestErrors = [];
    }

    getErrorMessages() {
        return this.manifestErrors;
    }

    setErrorMessages(errors: ErrorEntry[]) {
        this.manifestErrors = errors;
    }

    getDonePromise(): Promise<void> {
        if (!this.donePromise) {
            this.donePromise = Promise.withResolvers<void>();
        }
        return this.donePromise.promise;
    }

    async nextTick(increment: number): Promise<boolean> {
        const { pendingCommands } = this;
        this.pendingCommands = [];
        await Promise.all(pendingCommands);
        if (!this.settings || (this.progress.finished && this.pending.length === 0)) {
            return true;
        }
        let { pct, finished } = this.progress;
        pct = Math.min(pct + increment, 100);
        finished ||= pct >= 100;
        const generators: GenerateServerEvent[] = [];
        while (this.pending.length > 0 && this.pending[0].pct <= pct) {
            const { generate } = this.pending.shift();
            generators.push(generate);
        }
        finished ||= this.pending.length === 0;
        if (pct !== this.progress.pct || finished !== this.progress.finished) {
            this.progress = {
                ...this.progress,
                pct,
                finished,
            };
            this.dispatchEvent('progress', this.progress);
        }
        for (const generate of generators) {
            const [name, payload] = await generate(pct);
            this.dispatchEvent(name, payload);
        }
        return this.progress.finished
    }

    on = (event: string, cb: WebsocketEventListener) => {
        this.listeners.set(event, cb);
        return this.sock;
    };

    off = (event: string) => {
        this.listeners.delete(event);
        return this.sock;
    };

    emit = (event: string, data: object) => {
        if (event !== 'cmd') {
            throw new Error(`unknown event "${event}"`);
        }
        const { method, ...params } = data as ServerCommand;
        if (!method) {
            throw new Error('method parameter missing');
        }
        // don't wait for Promise to complete, to simulate that the
        // emit command is async
        this.pendingCommands.push(this.processCommand(method, params));
        return this.sock;
    }

    private async processCommand(method: string, params: object) {
        switch (method) {
            case 'validate':
                await this.startValidation(params as ValidatorSettings);
                break;
            case 'cancel':
                await this.cancelValidation();
                break;
            case 'save':
                await this.installStream(params as InstallStreamCommand);
                break;
            case 'done':
                // this is where the real server would wait to join to validator task
                this.donePromise?.resolve();
                this.donePromise = undefined;
                break;
            default:
                this.dispatchEvent('log', {
                    level: 'error',
                    text: `Unsupported command "${method}"`,
                });
        }
    }

    private async startValidation(settings: ValidatorSettings) {
        const errs = checkValidatorSettings(settings, []);
        if (Object.keys(errs).length > 0) {
            this.dispatchEvent('validate-errors', errs);
            this.progress = {
                pct: 0,
                text: 'invalid settings',
                aborted: false,
                finished: true,
            };
            return;
        }
        this.settings = settings;
        this.progress = {
            pct: 0,
            text: '',
            aborted: false,
            finished: false,
        };
        log.debug(`starting validation of ${settings.manifest} duration=${settings.duration}`);
        this.pending = [
            mkInfoEvent(0.2, "Starting stream validation...",),
            {
                pct: 0.5,
                generate: this.generateManifestEvent,
            },
            mkInfoEvent(1, "Prefetching media files required before validation can start"),
            {
                pct: 100,
                generate: async () => ['codecs', exampleCodecs.map(({ codec }) => codec)],
            },
        ];
        if (this.manifestErrors.length) {
            this.pending.push(mkInfoEvent(100, `Found ${this.manifestErrors.length} errors`));
            this.pending.push({
                pct: 100,
                generate: async () => ['manifest-errors', this.manifestErrors],
            });
        }
        this.pending.push(mkInfoEvent(100, `Validation complete after ${settings.duration} seconds`));
        if (settings.save) {
            this.pending.push({
                pct: 100,
                generate: async () => [
                    'install', {
                        filename: 'dv-new-stream.json',
                        prefix: settings.prefix,
                        title: settings.title,
                    }],
            });
        }
        this.pending.push({
            pct: 100,
            generate: async () => [
                'finished', {
                    startTime: Date.now(),
                    endTime: Date.now() + 1000 * settings.duration,
                    aborted: false,
                }],
        });
    }

    private async cancelValidation() {
        const stopPct = this.progress.pct + 3;
        log.debug(`cancelling validation at ${stopPct}%`);
        this.pending = this.pending.filter((item) => item.pct <= stopPct);
        const dur = this.settings.duration * stopPct / 100;
        this.pending.push(mkInfoEvent(stopPct, `Validation aborted after ${dur} seconds`));
        this.pending.push({
            pct: stopPct,
            generate: async () => [
                'finished', {
                    startTime: Date.now(),
                    endTime: Date.now() + 1000 * dur,
                    aborted: true,
                }],
        });
        this.progress = {
            ...this.progress,
            aborted: true,
        };
    }

    private async installStream({ filename, title, prefix }: InstallStreamCommand) {
        this.dispatchEvent("log", {
            level: "info",
            text: `Adding new stream ${prefix}: "${title}"`,
        });
        this.dispatchEvent("log", {
            level: "debug",
            text: `Installing ${filename}`,
        });
        const last = this.pending.pop();
        this.pending.push(mkInfoEvent(100, 'Adding new stream complete'));
        if (last) {
            this.pending.push(last);
        }
    }

    private dispatchEvent(ev: string, data: unknown) {
        log.trace(`dispatchEvent(${ev})`, data);
        const cb = this.listeners.get(ev);
        cb?.(data);
    }

    private generateManifestEvent: GenerateServerEvent = async () => {
        const url = new URL(this.settings.manifest);
        const mpd = await this.endpoint.fetchFixtureText(url.pathname);
        const mpdEv: ManifestEvent = {
            text: mpd.split('\n'),
        };
        return ['manifest', mpdEv];
    };
}

function mkInfoEvent(pct: number, text: string): PendingServerEvent {
    return {
        pct,
        generate: () => Promise.resolve(["log", { text, level: "info" }]),
    };
}
