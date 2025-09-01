import { vi, describe, test, expect, afterEach } from "vitest";
import { NativePlayer } from "./NativePlayer";

describe('NativePlayer', () => {
    const mpdSource = 'http://example.local/manifest.mpd';
    const logEvent = vi.fn();
    const tracksChanged = vi.fn();
    const textEnabled = false;
    const textLanguage = "";

    afterEach(() => {
        vi.clearAllMocks();
    });

    test('can create NativePlayer', async () => {
        const videoElement = document.createElement('video');
        const addEventSpy = vi.spyOn(videoElement, 'addEventListener');
        const player = new NativePlayer({
            logEvent,
            tracksChanged,
            videoElement,
            textEnabled,
            textLanguage,
         });
        await player.initialize(mpdSource);
        expect(addEventSpy).not.toHaveBeenCalled();
        expect(videoElement.src).toEqual(mpdSource);
        player.destroy();
    });

    test('can auto play', async () => {
        const videoElement = document.createElement('video');
        const addEventSpy = vi.spyOn(videoElement, 'addEventListener');
        const player = new NativePlayer({
            logEvent,
            tracksChanged,
            videoElement,
            textEnabled,
            textLanguage,
            autoplay: true
        });
        await player.initialize(mpdSource);
        expect(addEventSpy).toHaveBeenCalledWith('canplay', expect.any(Function));
        player.destroy();
    });
});