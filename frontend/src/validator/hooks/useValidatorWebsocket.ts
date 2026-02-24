import { useCallback, useEffect, useMemo, useRef } from 'preact/hooks';
import { batch, type ReadonlySignal, useComputed, useSignal } from '@preact/signals';
import { io } from 'socket.io-client';
import { decode } from 'codec-string';

import { LogEntry } from '../types/LogEntry';
import { ProgressState } from '../types/ProgressState';
import { CodecInformation } from '../types/CodecInformation';
import { ErrorEntry } from '../types/ErrorEntry';
import { ManifestLine } from '../types/ManifestLine';
import { ManifestEvent } from '../types/ManifestEvent';
import { ValidatorSettings } from '../types/ValidatorSettings';

export interface ValidatorProgressEvent {
    pct: number;
    text: string;
    aborted?: boolean;
    finished?: boolean;
}

export interface ValidatorErrorEvent {
    manifest?: string;
    duration?: string;
    prefix?: string;
    title?: string;
}

export interface ValidatorFinishedEvent {
    startTime: number;
    endTime: number;
    aborted: boolean;
}

export interface InstallStreamCommand {
    filename: string;
    title: string;
    prefix: string;
}

type SocketEventListeners = {
    connect: () => void;
    codecs: (codecNames: string[]) => void;
    disconnect: () => void;
    error: (err: Error) => void;
    finished: (data: ValidatorFinishedEvent) => void;
    install: (cmd: InstallStreamCommand) => void;
    log: (msg: Omit<LogEntry, 'id'>) => void;
    manifest: (ev: ManifestEvent) => void;
    'manifest-errors': (data: ErrorEntry[]) => void;
    progress: (ev: ValidatorProgressEvent) => void;
    'validate-errors': (ev: ValidatorErrorEvent) => void;
};

export enum ValidatorState {
    DISCONNECTED = 'disconnected',
    IDLE = 'idle',
    ACTIVE = 'active',
    CANCELLING = 'cancelling',
    CANCELLED = 'cancelled',
    DONE = 'done',
    CONNECTION_FAILED = 'connection-failed'
}

export interface UseValidatorWebsocketHook {
    codecs: ReadonlySignal<CodecInformation[]>;
    errors: ReadonlySignal<ErrorEntry[]>;
    log: ReadonlySignal<LogEntry[]>;
    manifest: ReadonlySignal<ManifestLine[]>;
    progress: ReadonlySignal<ProgressState>;
    state: ReadonlySignal<ValidatorState>;
    result: ReadonlySignal<ValidatorFinishedEvent|undefined>;
    start: (settings: ValidatorSettings) => void;
    cancel: () => void;
}

export function useValidatorWebsocket(wssUrl: string): UseValidatorWebsocketHook {
    const socket = useMemo(() => io(wssUrl, { autoConnect: false, timeout: 10_000 }), [wssUrl]);
    const log = useSignal<LogEntry[]>([]);
    const progress = useSignal<ProgressState>({ minValue: 0, maxValue: 100, finished: false, error: false, text: ''});
    const manifestText = useSignal<string[]>([]);
    const codecs = useSignal<CodecInformation[]>([]);
    const errors = useSignal<ErrorEntry[]>([]);
    const state = useSignal<ValidatorState>(ValidatorState.DISCONNECTED);
    const result = useSignal<ValidatorFinishedEvent|undefined>();
    const manifest = useComputed<ManifestLine[]>(() => {
        const lines: ManifestLine[] = manifestText.value.map((text: string, idx: number) => ({
            text,
            line: idx + 1,
            hasError: false,
            errors: [],
        }));
        for (const err of errors.value) {
            const { location, clause, msg } = err;
            const [ start, end ] = location;
            const text = clause ? `${clause}: ${msg}` : msg;
            for(let i=start; i <= end; ++i) {
                lines[i - 1].hasError = true;
            }
            lines[start - 1].errors.push(text);
        }
        return lines;
    });
    const nextMsgId = useRef<number>(1);

    const addLogMessage = useCallback((msg: Omit<LogEntry, 'id'>) => {
        log.value = [
            ...log.value,
            {
                ...msg,
                id: nextMsgId.current,
            },
        ];
        nextMsgId.current += 1;
    }, [log]);

    const listeners: SocketEventListeners = useMemo(() => ({
        connect: () => {
            state.value = ValidatorState.IDLE;
        },
        disconnect: () => {
            state.value = ValidatorState.DISCONNECTED;
        },
        error: (err: Error) => {
            console.error(`Websocket connection failed: ${err}`);
            state.value = ValidatorState.CONNECTION_FAILED;
            const msg: LogEntry = {
                id: 0,
                level: "error",
                text: err.message,
            };
            addLogMessage(msg);
        },
        log: addLogMessage,
        progress: (data: ValidatorProgressEvent) => {
            const { aborted, pct, text, finished } = data;
            batch(() => {
                progress.value = {
                    ...progress.value,
                    text,
                    finished,
                    error: aborted,
                    currentValue: Math.round(10 * pct) / 10,
                };
            });
            if (finished) {
                socket.emit('cmd', { method: 'done' });
            }
        },
        manifest: ({ text }: ManifestEvent) => {
            manifestText.value = text;
        },
        codecs: (codecNames: string[]) => {
            const data: CodecInformation[] = codecNames.map((codec: string) => {
                const { error, decodes } = decode(codec);
                const ci: CodecInformation = {
                    codec,
                    error,
                    details: decodes.map(({parsed, error, label}) => ({
                        label,
                        error,
                        details: parsed.map(p => p.decode),
                    })),
                };
                return ci;
            });
            codecs.value = data;
        },
        'manifest-errors': (data: ErrorEntry[]) => {
            errors.value = data;
        },
        finished: (data: ValidatorFinishedEvent) => {
            batch(() => {
                if (state.value == ValidatorState.CANCELLING) {
                    state.value = ValidatorState.CANCELLED;
                } else if (state.value == ValidatorState.ACTIVE) {
                    state.value = ValidatorState.DONE;
                }
                progress.value = {
                    ...progress.value,
                    finished: true,
                };
                result.value = data;
            });
        },
        install: ({ filename, title, prefix }: InstallStreamCommand) => {
            addLogMessage({
                level: 'info',
                text: `Installing new stream from ${filename}`,
            });
            socket.emit('cmd', {
                method: 'save',
                filename,
                prefix,
                title,
            });
        },
        'validate-errors': (data: ValidatorErrorEvent) => {
            batch(() => {
                for (const text of Object.values(data)) {
                    addLogMessage({
                        level: 'error',
                        text,
                    });
                }
                progress.value = {
                    ...progress.value,
                    finished: true,
                };
                result.value = {
                    startTime: Date.now(),
                    endTime: Date.now(),
                    aborted: true,
                };
                state.value = ValidatorState.DONE;
            });
        },
    }), [addLogMessage, codecs, errors, manifestText, progress, result, socket, state]);

    const start = useCallback((settings: ValidatorSettings) => {
        if (state.value === ValidatorState.CONNECTION_FAILED || state.value === ValidatorState.DISCONNECTED) {
            const msg: LogEntry = {
                id: 0,
                level: 'error',
                text: 'Cannot start validation as not connected',
            };
            addLogMessage(msg);
            return;
        }
        batch(() => {
            state.value = ValidatorState.ACTIVE;
            manifestText.value = [];
            log.value = [];
            errors.value = [];
            progress.value = {
                minValue: 0, maxValue: 100, finished: false, error: false, text: ''
            };
            result.value = undefined;
        });
        socket.emit('cmd', {
            method: 'validate',
            ...settings,
        });
    }, [addLogMessage, errors, log, manifestText, progress, result, socket, state]);

    const cancel = useCallback(() => {
        batch(() => {
            state.value = ValidatorState.CANCELLING;
            progress.value = {
                ...progress.value,
                error: true,
            };
        });
        socket.emit('cmd', {
            method: 'cancel',
        });
    }, [progress, socket, state]);

    useEffect(() => {
        for (const [name, handler] of Object.entries(listeners)) {
            socket.on(name, handler);
        }
        socket.connect();

        return () => {
            for (const [name, handler] of Object.entries(listeners)) {
                socket.off(name, handler);
            }
            socket.disconnect();
        };
    }, [addLogMessage, listeners, socket]);

    return { codecs, errors, log, manifest, progress, result, state, start, cancel };
}
