import { vi, describe, test, expect, beforeEach, afterEach } from "vitest";
import { mock, mockReset } from "vitest-mock-extended";
import type shaka from 'shaka-player';

import { importLibrary } from "./importLibrary";
import { AllDrmOptions, ShakaConfig, ShakaPlayer, ShakaTextTrack } from "./ShakaPlayer";
import { OptionMapWithChildren } from "@dashlive/options";
import { MediaTrack } from "../types/MediaTrack";
import { MediaTrackType } from "../types/MediaTrackType";

vi.mock("./importLibrary", () => {
    return {
        importLibrary: vi.fn(),
    };
});

interface WindowWithShaka extends Window {
    shaka: {
        polyfill: {
            installAll: () => void,
        },
        log: {
            setLevel: (level: unknown) => void,
            Level: {
                V1: string,
            },
        },
        Player: () => shaka.Player;
        util: {
            EventManager: () => shaka.util.EventManager,
        },
    }
}

describe('ShakaPlayer', () => {
    const mpdSource = 'http://example.local/manifest.mpd';
    const mockedImportLibrary = vi.mocked(importLibrary);
    const logEvent = vi.fn();
    const tracksChanged = vi.fn();
    const PlayerFactory = vi.fn();
    const EventManagerFactory = vi.fn();
    const videoElement = mock<HTMLVideoElement>();
    const mockPlayer = mock<shaka.Player>();
    const mockEventManager = mock<shaka.util.EventManager>();
    const installAll = vi.fn();
    const shakaTextTrack: ShakaTextTrack = {
        id: 2,
        active: false,
        language: "eng",
        label: "label",
    };
    const textMediaTrack: MediaTrack = {
        id: `${shakaTextTrack.id}`,
        trackType: MediaTrackType.TEXT,
        language: shakaTextTrack.language,
        active: false
    };

    let eventTarget: EventTarget;

    beforeEach(() => {
        shakaTextTrack.active = false;
        eventTarget = new EventTarget();
        mockPlayer.addEventListener.mockImplementation((evName: string, fn: () => void) => {
            eventTarget.addEventListener(evName, fn as EventListener);
        });
        mockPlayer.removeEventListener.mockImplementation((evName: string, fn: () => void) => {
            eventTarget.removeEventListener(evName, fn as EventListener);
        });
        mockPlayer.getTextTracks.mockReturnValue([shakaTextTrack as unknown as shaka.extern.Track]);
        mockEventManager.listen.mockImplementation((target: EventTarget, evName: string, fn: () => void) => {
            if (target === mockPlayer) {
                eventTarget.addEventListener(evName, fn as EventListener);
            }
        });
        PlayerFactory.mockReturnValue(mockPlayer);
        EventManagerFactory.mockReturnValue(mockEventManager);
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
                util: {
                    EventManager: EventManagerFactory,
                },
            };
        });
    });

    afterEach(() => {
        vi.clearAllMocks();
        mockReset(mockPlayer);
        mockReset(mockEventManager);
    });

    test.each(ShakaPlayer.LOCAL_VERSIONS)('can use Shaka version %s', async (version: string) => {
        const jsUrl = ShakaPlayer.cdnTemplate(version);
        const player = new ShakaPlayer({
            logEvent,
            version,
            videoElement,
            tracksChanged,
            textEnabled: true, textLanguage: "eng",
        });
        await player.initialize(mpdSource, {});
        expect(mockedImportLibrary).toHaveBeenCalledWith(jsUrl);
        expect(PlayerFactory).toHaveBeenCalledTimes(1);
        expect(installAll).toHaveBeenCalledTimes(1);
        expect(mockPlayer.attach).toHaveBeenCalledWith(videoElement);
        expect(mockPlayer.load).toHaveBeenLastCalledWith(mpdSource);
        let styles = document.head.querySelectorAll('link');
        expect(styles[0].href).toContain('shaka/controls.css');
        expect(styles.length).toEqual(1)
        eventTarget.dispatchEvent(new CustomEvent('loaded'));
        expect(logEvent).toHaveBeenCalledTimes(1);
        expect(logEvent).toHaveBeenCalledWith('loaded', '');
        player.destroy();
        expect(mockPlayer.destroy).toHaveBeenCalledTimes(1);
        styles = document.head.querySelectorAll('link');
        expect(styles.length).toEqual(0)
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
        const player = new ShakaPlayer({
            logEvent,
            version: ShakaPlayer.LOCAL_VERSIONS[0],
            videoElement,
            tracksChanged,
            textEnabled: true,
            textLanguage: "cym",
        });
        await player.initialize(mpdSource, options as unknown as OptionMapWithChildren);
        const shakaConfig: ShakaConfig = {
            drm: {
                servers: {
                    'com.microsoft.playready': options.playready.licenseUrl
                },
            },
            preferredTextLanguage: 'cym',
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
        const player = new ShakaPlayer({
            logEvent,
            tracksChanged,
            version: ShakaPlayer.LOCAL_VERSIONS[0],
            videoElement,
            textEnabled: false,
            textLanguage: 'fra',
        });
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
        mockPlayer.load.mockImplementation(async () => {
            throw new Error('Load failed');
        });
        const player = new ShakaPlayer({
            logEvent,
            tracksChanged,
            version: ShakaPlayer.LOCAL_VERSIONS[0],
            videoElement,
            textEnabled: false,
            textLanguage: '',
        });
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
        const player = new ShakaPlayer({
            logEvent,
            version: ShakaPlayer.LOCAL_VERSIONS[0],
            videoElement,
            tracksChanged,
            textEnabled: false,
            textLanguage: '',
        });
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

    test('can set subtitles element before initialize', async () => {
        const subsElt = document.createElement('div');
        const player = new ShakaPlayer({
            logEvent,
            videoElement,
            tracksChanged,
            autoplay: true,
            version: ShakaPlayer.LOCAL_VERSIONS[0],
            textEnabled: true,
            textLanguage: "gre",
        });
        player.setSubtitlesElement(subsElt);
        await player.initialize(mpdSource, {});
        expect(mockPlayer.setVideoContainer).toHaveBeenCalledTimes(1);
        expect(mockPlayer.setVideoContainer).toHaveBeenCalledWith(subsElt);
    });

    test('can set subtitles element after initialize', async () => {
        const subsElt = document.createElement('div');
        const player = new ShakaPlayer({
            logEvent,
            videoElement,
            tracksChanged,
            autoplay: true,
            version: ShakaPlayer.LOCAL_VERSIONS[0],
            textEnabled: true,
            textLanguage: "pol",
        });
        await player.initialize(mpdSource, {});
        expect(mockPlayer.setVideoContainer).not.toHaveBeenCalled();
        player.setSubtitlesElement(subsElt);
        expect(mockPlayer.setVideoContainer).toHaveBeenCalledTimes(1);
        expect(mockPlayer.setVideoContainer).toHaveBeenCalledWith(subsElt);
    });

    test('can set text track', async () => {
        const subsElt = document.createElement('div');
        const player = new ShakaPlayer({
            logEvent,
            videoElement,
            tracksChanged,
            autoplay: true,
            version: ShakaPlayer.LOCAL_VERSIONS[0],
            textEnabled: true,
            textLanguage: shakaTextTrack.language,
        });
        await player.initialize(mpdSource, {});
        player.setSubtitlesElement(subsElt);
        expect(mockPlayer.setTextTrackVisibility).not.toHaveBeenCalled();
        player.setTextTrack(textMediaTrack);
        expect(mockPlayer.setTextTrackVisibility).toHaveBeenCalledTimes(1);
        expect(mockPlayer.setTextTrackVisibility).toHaveBeenLastCalledWith(true);
        expect(mockPlayer.selectTextTrack).toHaveBeenCalledTimes(1);
        expect(mockPlayer.selectTextTrack).toHaveBeenLastCalledWith(expect.objectContaining({
            ...shakaTextTrack
        }));
        player.setTextTrack(null);
        expect(mockPlayer.setTextTrackVisibility).toHaveBeenCalledTimes(2);
        expect(mockPlayer.setTextTrackVisibility).toHaveBeenLastCalledWith(false);
    });

    test('calls setTracks after loading and when track list changes', async () => {
        const player = new ShakaPlayer({
            logEvent,
            videoElement,
            tracksChanged,
            autoplay: true,
            version: ShakaPlayer.LOCAL_VERSIONS[0],
            textEnabled: true,
            textLanguage: shakaTextTrack.language,
        });
        await player.initialize(mpdSource, {});
        expect(mockEventManager.listen).toHaveBeenCalledWith(expect.anything(), 'loaded', expect.any(Function));
        const loadedHandler = mockEventManager.listen.mock.calls.find((call => call[1] === 'loaded'))?.[2];
        expect(loadedHandler).toBeDefined();
        expect(tracksChanged).not.toHaveBeenCalled();
        expect(shakaTextTrack.active).toEqual(false);
        const ev = mock<Event>();
        loadedHandler?.(ev);
        expect(tracksChanged).toHaveBeenCalledTimes(1);
        const expectedTracks: MediaTrack[] = [textMediaTrack];
        expect(tracksChanged).toHaveBeenLastCalledWith(expectedTracks);
        shakaTextTrack.active = true;
        expect(mockEventManager.listen).toHaveBeenCalledWith(expect.anything(), 'trackschanged', expect.any(Function));
        const changeHandler = mockEventManager.listen.mock.calls.find((call => call[1] === 'trackschanged'))?.[2];
        expect(changeHandler).toBeDefined();
        changeHandler?.(ev);
        expect(tracksChanged).toHaveBeenCalledTimes(2);
        expectedTracks[0].active = true;
        expect(tracksChanged).toHaveBeenLastCalledWith(expectedTracks);
        player.destroy();
    });


});