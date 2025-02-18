import { act, renderHook } from "@testing-library/preact";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { mock, mockReset } from "vitest-mock-extended";
import { io, Socket } from 'socket.io-client';
import log from 'loglevel';

import { useValidatorWebsocket, ValidatorState } from "./useValidatorWebsocket";
import { MockWebsocketServer } from "../../test/MockWebsocketServer";
import { ValidatorSettings } from "../types/ValidatorSettings";
import { exampleCodecs } from "../../test/fixtures/exampleCodecs";

vi.mock('socket.io-client');

describe('useValidatorWebsocket hook', () => {
    const ioMock = vi.mocked(io);
    const mockSocket = mock<Socket>();
    const wssUrl = 'wss://localhost:3456';
    const settings: ValidatorSettings = {
        duration: 16,
        encrypted: false,
        manifest: 'http://localhost:8765/dash/vod/bbb/hand_made.mpd',
        media: true,
        prefix: '',
        pretty: false,
        save: false,
        title: '',
        verbose: false,
    };
    const expectedEvents: string[] = [
        'codecs',
        'connect',
        'disconnect',
        'finished',
        'install',
        'log',
        'manifest',
        'manifest-errors',
        'progress',
        'validate-errors',
    ];
    let server: MockWebsocketServer;

    beforeEach(() => {
        ioMock.mockImplementation(() => mockSocket);
        server = MockWebsocketServer.create(wssUrl, mockSocket).server;
    });

    afterEach(async () => {
        await server.destroy();
        vi.clearAllMocks();
        mockReset(mockSocket);
        vi.useRealTimers();
        log.setLevel('error');
    });

    test('can open Websocket', async () => {
        vi.useFakeTimers();
        const connected = server.getConnectedPromise();
        const { result } = renderHook((url: string) => useValidatorWebsocket(url), {
            initialProps: wssUrl
        });
        expect(ioMock).toHaveBeenCalledTimes(1);
        expect(ioMock).toHaveBeenCalledWith(wssUrl, {
            autoConnect: false,
        });
        expect(mockSocket.on).toHaveBeenCalledTimes(expectedEvents.length);
        expectedEvents.forEach(ev => expect(mockSocket.on).toHaveBeenCalledWith(ev, expect.any(Function)));
        expect(result.current.log.value).toEqual([]);
        expect(result.current.state.value).toEqual(ValidatorState.DISCONNECTED);
        await vi.advanceTimersByTimeAsync(1000);
        await expect(connected).resolves.toBeUndefined();
        expect(result.current.state.value).toEqual(ValidatorState.IDLE);
    });

    test('closes connection when unmounted', async () => {
        const connected = server.getConnectedPromise();
        const { result, unmount } = renderHook((url: string) => useValidatorWebsocket(url), {
            initialProps: wssUrl
        });
        await expect(connected).resolves.toBeUndefined();
        expect(server.getIsConnected()).toEqual(true);
        expect(result.current.state.value).toEqual(ValidatorState.IDLE);
        await act(async () => {
            unmount();
        });
        expect(server.getIsConnected()).toEqual(false);
        expectedEvents.forEach(ev => expect(mockSocket.off).toHaveBeenCalledWith(ev, expect.any(Function)));
    });

    test('detects if server disconnects', async () => {
        const connected = server.getConnectedPromise();
        const { result } = renderHook((url: string) => useValidatorWebsocket(url), {
            initialProps: wssUrl
        });
        await expect(connected).resolves.toBeUndefined();
        await act(async () => {
            server.disconnect();
            await server.nextTick(0);
        });
        expect(result.current.state.value).toEqual(ValidatorState.DISCONNECTED);
    });

    test('validate a stream', async () => {
        const connected = server.getConnectedPromise();
        const { result } = renderHook((url: string) => useValidatorWebsocket(url), {
            initialProps: wssUrl
        });
        await expect(connected).resolves.toBeUndefined();
        const { start, codecs, progress, state, result: valResult, log, manifest } = result.current;
        start(settings);
        const timeout = Date.now() + 20_000;
        while (!progress.value.finished || valResult.value === undefined) {
            if (Date.now() > timeout) {
                throw new Error('test timeout');
            }
            await act(async () => {
                await server.nextTick(0.5);
            });
        }
        expect(log.value).toEqual([
            {
                level: 'info',
                text: 'Starting stream validation...',
                id: 1
            },
            {
                level: 'info',
                text: 'Prefetching media files required before validation can start',
                id: 2
            },
            {
                level: 'info',
                text: 'Validation complete after 16 seconds',
                id: 3
            }
        ]);
        expect(manifest.value.length).toEqual(161);
        expect(codecs.value).toEqual(exampleCodecs);
        expect(valResult.value).toEqual({
            aborted: false,
            startTime: expect.any(Number),
            endTime: expect.any(Number),
        });
        expect(mockSocket.emit).toHaveBeenNthCalledWith(1, "cmd", {
            ...settings,
            method: 'validate',
        });
        expect(state.value).toEqual(ValidatorState.DONE);
        expect(manifest.value).toMatchSnapshot();
    });

    test('validate a stream that has errors', async () => {
        server.setErrorMessages([
            {
                assertion: {
                    filename: "period.py",
                    line: 345,
                },
                location: [20, 30],
                clause: "1.2.3",
                msg: "validator assertion message",
            },
            {
                assertion: {
                    filename: "representation.py",
                    line: 123,
                },
                location: [120, 130],
                msg: "representation has an error",
            },
        ]);
        const { result } = renderHook((url: string) => useValidatorWebsocket(url), {
            initialProps: wssUrl
        });
        await expect(server.getConnectedPromise()).resolves.toBeUndefined();
        const { start, errors, progress, result: valResult, manifest } = result.current;
        start(settings);
        const timeout = Date.now() + 20_000;
        while (!progress.value.finished) {
            if (Date.now() > timeout) {
                throw new Error('test timeout');
            }
            await act(async () => {
                await server.nextTick(0.5);
            });
        }
        expect(errors.value).toEqual(server.getErrorMessages());
        expect(manifest.value).toMatchSnapshot();
        expect(valResult.value).toEqual({
            aborted: false,
            startTime: expect.any(Number),
            endTime: expect.any(Number),
        });
    });

    test('can abort validation', async () => {
        const { result } = renderHook((url: string) => useValidatorWebsocket(url), {
            initialProps: wssUrl
        });
        await expect(server.getConnectedPromise()).resolves.toBeUndefined();
        const { start, cancel, progress, state, result: valResult, log, manifest } = result.current;
        let aborted = false;
        start(settings);
        const timeout = Date.now() + 20_000;
        while (!progress.value.finished || valResult.value === undefined) {
            if (Date.now() > timeout) {
                throw new Error('test timeout');
            }
            await act(async () => {
                await server.nextTick(0.5);
            });
            if (progress.value.currentValue > 5 && !aborted) {
                aborted = true;
                cancel();
                expect(state.value).toEqual(ValidatorState.CANCELLING)
            }
        }
        expect(manifest.value.length).toEqual(161);
        expect(log.value[log.value.length - 1]).toEqual({
            text: expect.stringContaining('Validation aborted after'),
            level: 'info',
            id: expect.any(Number),
        });
        expect(state.value).toEqual(ValidatorState.CANCELLED);
        expect(valResult.value).toEqual({
            aborted: true,
            startTime: expect.any(Number),
            endTime: expect.any(Number),
        });
    });

    test('save a stream', async () => {
        const { result } = renderHook((url: string) => useValidatorWebsocket(url), {
            initialProps: wssUrl
        });
        await expect(server.getConnectedPromise()).resolves.toBeUndefined();
        const { start, progress, state, result: valResult, log } = result.current;
        const saveSettings: ValidatorSettings = {
            ...settings,
            save: true,
            prefix: 'ptst',
            title: 'testing saving a stream',
        };
        start(saveSettings);
        const timeout = Date.now() + 20_000;
        while (!progress.value.finished || valResult.value === undefined) {
            if (Date.now() > timeout) {
                throw new Error('test timeout');
            }
            await act(async () => {
                await server.nextTick(0.5);
            });
        }
        expect(log.value).toEqual([
            {
                level: 'info',
                text: 'Starting stream validation...',
                id: 1
            },
            {
                level: 'info',
                text: 'Prefetching media files required before validation can start',
                id: 2
            },
            {
                level: 'info',
                text: 'Validation complete after 16 seconds',
                id: 3
            },
            {
                id: 4,
                level: "info",
                text: expect.stringContaining("Installing new stream"),
            },
            {
                id: 5,
                level: "info",
                text: "Adding new stream ptst: \"testing saving a stream\"",
            },
            {
                id: 6,
                level: "debug",
                text: "Installing dv-new-stream.json",
            },
        ]);
        expect(state.value).toEqual(ValidatorState.DONE);
    });

    test('save a stream with invalid settings', async () => {
        const { result } = renderHook((url: string) => useValidatorWebsocket(url), {
            initialProps: wssUrl
        });
        await expect(server.getConnectedPromise()).resolves.toBeUndefined();
        const { start, progress, state, result: valResult, log } = result.current;
        const saveSettings: ValidatorSettings = {
            ...settings,
            save: true,
        };
        start(saveSettings);
        const timeout = Date.now() + 20_000;
        while (!progress.value.finished || valResult.value === undefined) {
            if (Date.now() > timeout) {
                throw new Error('test timeout');
            }
            await act(async () => {
                await server.nextTick(0.5);
            });
        }
        expect(log.value).toEqual([
            { level: 'error', text: 'a directory name is required', id: 1 },
            { level: 'error', text: 'a title is required', id: 2 }
        ]);
        expect(state.value).toEqual(ValidatorState.DONE);
    });
});