import { act, renderHook } from "@testing-library/preact";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { mock, mockReset } from "vitest-mock-extended";
import { io, Socket } from 'socket.io-client';

import { useValidatorWebsocket, ValidatorState } from "./useValidatorWebsocket";
import { MockWebsocketServer } from "../../test/MockWebsocketServer";
import { ValidatorSettings } from "../types/ValidatorSettings";
import { FakeEndpoint } from "../../test/FakeEndpoint";
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
        'finished',
        'install',
        'log',
        'manifest',
        'manifest-errors',
        'progress',
    ];
    let endpoint: FakeEndpoint;
    let server: MockWebsocketServer;

    beforeEach(() => {
        ioMock.mockImplementation(() => mockSocket);
        endpoint = new FakeEndpoint(wssUrl);
        server = new MockWebsocketServer(mockSocket, endpoint);
        mockSocket.on.mockImplementation(server.on);
        mockSocket.off.mockImplementation(server.off);
        mockSocket.emit.mockImplementation(server.emit);
    });

    afterEach(() => {
        server.destroy();
        vi.clearAllMocks();
        mockReset(mockSocket);
    });

    test('can open Websocket', () => {
        const { result } = renderHook((url: string) => useValidatorWebsocket(url), {
            initialProps: wssUrl
        });
        expect(ioMock).toHaveBeenCalledTimes(1);
        expect(ioMock).toHaveBeenCalledWith(wssUrl);
        expect(mockSocket.on).toHaveBeenCalledTimes(expectedEvents.length);
        expectedEvents.forEach(ev => expect(mockSocket.on).toHaveBeenCalledWith(ev, expect.any(Function)));
        expect(result.current.log.value).toEqual([]);
    });

    test('validate a stream', async () => {
        const { result } = renderHook((url: string) => useValidatorWebsocket(url), {
            initialProps: wssUrl
        });
        const { start, codecs, progress, state, result: valResult, log, manifest } = result.current;
        start(settings);
        while (!progress.value.finished || valResult.value === undefined) {
            await act(async () => {
                await server.nextTick(0.1);
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
                clause: "3.4.5",
                msg: "representation has an error",
            },
        ]);
        const { result } = renderHook((url: string) => useValidatorWebsocket(url), {
            initialProps: wssUrl
        });
        const { start, errors, progress, result: valResult, manifest } = result.current;
        start(settings);
        while (!progress.value.finished) {
            await act(async () => {
                await server.nextTick(0.1);
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
        const { start, cancel, progress, state, result: valResult, log, manifest } = result.current;
        let aborted = false;
        start(settings);
        while (!progress.value.finished || valResult.value === undefined) {
            await act(async () => {
                await server.nextTick(0.1);
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
        const { start, progress, state, result: valResult, log } = result.current;
        const saveSettings: ValidatorSettings = {
            ...settings,
            save: true,
            prefix: 'ptst',
            title: 'testing saving a stream',
        };
        start(saveSettings);
        while (!progress.value.finished || valResult.value === undefined) {
            await act(async () => {
                await server.nextTick(0.1);
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

});