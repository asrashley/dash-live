import { vi, describe, test, expect, beforeEach, afterEach } from "vitest";
import { mock, mockClear } from "vitest-mock-extended";

import { importLibrary } from "./importLibrary";
import { AllDrmOptions, ShakaConfig, ShakaPlayer } from "./ShakaPlayer";
import { OptionMapWithChildren } from "@dashlive/options";

vi.mock("./importLibrary", () => {
    return {
        importLibrary: vi.fn(),
    };
});

interface ShakaPlayerClass {
    attach: (videoElement: HTMLVideoElement) => void;
    configure: (config: ShakaConfig) => void;
    addEventListener(evName: string, fn: () => void): void;
    removeEventListener(evName: string, fn: () => void): void;
    load: (mpd: string) => Promise<void>;
    destroy: () => void;
}

interface WindowWithShaka extends Window {
    shaka: {
        polyfill: {
            installAll: () => void,
        },
        log: {
            setLevel: (level: unknown) => void,
            Level: {
                V1: string;
            }
        }
        Player: () => ShakaPlayerClass;
    }
}

describe('ShakaPlayer', () => {
    const mpdSource = 'http://example.local/manifest.mpd';
    const mockedImportLibrary = vi.mocked(importLibrary);
    const logEvent = vi.fn();
    const PlayerFactory = vi.fn();
    const mockPlayer = mock<ShakaPlayerClass>();
    const installAll = vi.fn();
    let eventTarget: EventTarget;

    beforeEach(() => {
        eventTarget = new EventTarget();
        mockPlayer.addEventListener.mockImplementation((evName: string, fn: () => void) => {
            eventTarget.addEventListener(evName, fn as EventListener);
        });
        mockPlayer.removeEventListener.mockImplementation((evName: string, fn: () => void) => {
            eventTarget.removeEventListener(evName, fn as EventListener);
        });
        PlayerFactory.mockReturnValue(mockPlayer);
        mockPlayer.load.mockResolvedValue(undefined);
        mockedImportLibrary.mockImplementationOnce(async () => {
            (window as unknown as WindowWithShaka)["shaka"] = {
                polyfill: {
                    installAll,
                },
                log: {
                    setLevel: vi.fn(),
                    Level: {
                        V1: 'V1',
                    }
                },
                Player: PlayerFactory,
            };
        });
    });

    afterEach(() => {
        vi.clearAllMocks();
        mockClear(mockPlayer);
    });

    test.each(ShakaPlayer.LOCAL_VERSIONS)('can use Shaka version %s', async (version: string) => {
        const jsUrl = ShakaPlayer.cdnTemplate(version);
        const videoElement = document.createElement('video');
        const player = new ShakaPlayer({ logEvent, version, videoElement });
        await player.initialize(mpdSource, {});
        expect(mockedImportLibrary).toHaveBeenCalledWith(jsUrl);
        expect(PlayerFactory).toHaveBeenCalledTimes(1);
        expect(installAll).toHaveBeenCalledTimes(1);
        expect(mockPlayer.attach).toHaveBeenCalledWith(videoElement);
        expect(mockPlayer.load).toHaveBeenLastCalledWith(mpdSource);
        eventTarget.dispatchEvent(new CustomEvent('loaded'));
        expect(logEvent).toHaveBeenCalledTimes(1);
        expect(logEvent).toHaveBeenCalledWith('loaded', '');
        player.destroy();
        expect(mockPlayer.destroy).toHaveBeenCalledTimes(1);
    });

    test('can use an alternate Shaka version', () => {
        expect(ShakaPlayer.cdnTemplate('1.2.3')).toEqual('https://ajax.googleapis.com/ajax/libs/shaka-player/1.2.3/shaka-player.compiled.js');
    });

    test('can configure PlayReady DRM', async () => {
        const options: AllDrmOptions = {
            drmSelection: ['playready'],
            playready: {
                licenseUrl: 'https://example.local/license',
            },
            clearkey: {
                licenseUrl: null,
            },
            marlin: {
                licenseUrl: null,
            }
        };
        const videoElement = document.createElement('video');
        const player = new ShakaPlayer({ logEvent, version: ShakaPlayer.LOCAL_VERSIONS[0], videoElement });
        await player.initialize(mpdSource, options as unknown as OptionMapWithChildren);
        const shakaConfig: ShakaConfig = {
            drm: {
                servers: {
                    'com.microsoft.playready': options.playready.licenseUrl
                },
            },
        };
        expect(mockPlayer.configure).toHaveBeenCalledWith(shakaConfig);
    });

    test('can configure ClearKey DRM', async () => {
        const options: AllDrmOptions = {
            drmSelection: ['clearkey'],
            playready: {
                licenseUrl: null,
            },
            clearkey: {
                licenseUrl: 'https://example.local/license',
            },
            marlin: {
                licenseUrl: null,
            }
        };
        const videoElement = document.createElement('video');
        const player = new ShakaPlayer({ logEvent, version: ShakaPlayer.LOCAL_VERSIONS[0], videoElement });
        await player.initialize(mpdSource, options as unknown as OptionMapWithChildren);
        const shakaConfig: ShakaConfig = {
            drm: {
                servers: {
                    'org.w3.clearkey': options.clearkey.licenseUrl
                },
            },
        };
        expect(mockPlayer.configure).toHaveBeenCalledWith(shakaConfig);
    });

    test('handles load failing', async () => {
        const videoElement = document.createElement('video');
        mockPlayer.load.mockImplementation(async () => {
            throw new Error('Load failed');
        });
        const player = new ShakaPlayer({ logEvent, version: ShakaPlayer.LOCAL_VERSIONS[0], videoElement });
        await player.initialize(mpdSource, {});
        expect(PlayerFactory).toHaveBeenCalledTimes(1);
        expect(mockPlayer.attach).toHaveBeenCalledWith(videoElement);
        expect(mockPlayer.load).toHaveBeenCalledTimes(1);
        expect(mockPlayer.load).toHaveBeenLastCalledWith(mpdSource);
        expect(logEvent).toHaveBeenCalledTimes(1);
        expect(logEvent).toHaveBeenCalledWith('error', 'Error: Load failed');
        player.destroy();
        expect(mockPlayer.destroy).toHaveBeenCalledTimes(1);
    });

    test('logs errors', async () => {
        const videoElement = document.createElement('video');
        const player = new ShakaPlayer({ logEvent, version: ShakaPlayer.LOCAL_VERSIONS[0], videoElement });
        await player.initialize(mpdSource, {});
        expect(mockPlayer.attach).toHaveBeenCalledWith(videoElement);
        expect(mockPlayer.load).toHaveBeenLastCalledWith(mpdSource);
        eventTarget.dispatchEvent(new CustomEvent('error', {
            detail: {
                severity: 1,
                category: 2,
                code: 345,
            },
        }));
        expect(logEvent).toHaveBeenCalledTimes(1);
        expect(logEvent).toHaveBeenCalledWith('error', '1 - 2 - 345');
        eventTarget.dispatchEvent(new CustomEvent('error', {
            detail: new Error('generic error'),
        }));
        expect(logEvent).toHaveBeenCalledTimes(2);
        expect(logEvent).toHaveBeenLastCalledWith('error', 'Error: generic error');
        player.destroy();
        expect(mockPlayer.destroy).toHaveBeenCalledTimes(1);
    });
});