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
    const addEvent = vi.fn();
    const mockPlayer = mock<ShakaPlayerClass>();
    const installAll = vi.fn();

    beforeEach(() => {
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
                Player: vi.fn().mockReturnValue(mockPlayer),
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
        const player = new ShakaPlayer({ addEvent, version, videoElement });
        await player.initialize(mpdSource, {});
        expect(mockedImportLibrary).toHaveBeenCalledWith(jsUrl);
        expect(installAll).toHaveBeenCalledTimes(1);
        expect(mockPlayer.attach).toHaveBeenCalledWith(videoElement);
        expect(mockPlayer.load).toHaveBeenLastCalledWith(mpdSource);
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
        const player = new ShakaPlayer({ addEvent, version: ShakaPlayer.LOCAL_VERSIONS[0], videoElement });
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
        const player = new ShakaPlayer({ addEvent, version: ShakaPlayer.LOCAL_VERSIONS[0], videoElement });
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
});