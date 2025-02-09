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

export enum ValidatorState {
    IDLE = 'idle',
    ACTIVE = 'active',
    CANCELLING = 'cancelling',
    CANCELLED = 'cancelled',
    DONE = 'done',
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
    const socket = useMemo(() => io(wssUrl), [wssUrl]);
    const log = useSignal<LogEntry[]>([]);
    const progress = useSignal<ProgressState>({ minValue: 0, maxValue: 100, finished: false, error: false, text: ''});
    const manifestText = useSignal<string[]>([]);
    const codecs = useSignal<CodecInformation[]>([]);
    const errors = useSignal<ErrorEntry[]>([]);
    const state = useSignal<ValidatorState>(ValidatorState.IDLE);
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

    const onProgress = useCallback((data: ValidatorProgressEvent) => {
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
    }, [progress, socket]);

    const onManifest = useCallback(({ text }: ManifestEvent) => {
        manifestText.value = text;
    }, [manifestText]);

    const onCodecs = useCallback((codecNames: string[]) => {
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
    }, [codecs]);

    const onManifestErrors = useCallback((data: ErrorEntry[]) => {
        errors.value = data;
    }, [errors]);

    const onFinished = useCallback((data: ValidatorFinishedEvent) => {
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
    }, [progress, result, state]);

    const onInstallStream = useCallback(({ filename, title, prefix }: InstallStreamCommand) => {
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
    }, [addLogMessage, socket]);

    const start = useCallback((settings: ValidatorSettings) => {
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
    }, [errors, log, manifestText, progress, result, socket, state]);

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
        socket.on('codecs', onCodecs);
        socket.on('finished', onFinished);
        socket.on('install', onInstallStream);
        socket.on('log', addLogMessage);
        socket.on('manifest', onManifest);
        socket.on('manifest-errors', onManifestErrors);
        socket.on('progress', onProgress);

        return () => {
            socket.off('codecs', onCodecs);
            socket.off('finished', onFinished);
            socket.off('install', onInstallStream);
            socket.off('log', addLogMessage);
            socket.off('manifest', onManifest);
            socket.off('manifest-errors', onManifestErrors);
            socket.off('progress', onProgress);
        };
    }, [addLogMessage, onCodecs, onFinished, onManifest, onManifestErrors, onProgress, onInstallStream, socket]);

    return { codecs, errors, log, manifest, progress, result, state, start, cancel };
}
