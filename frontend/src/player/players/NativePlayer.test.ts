import { vi, describe, test, expect, afterEach, beforeEach } from "vitest";
import { mock, mockReset } from "vitest-mock-extended";
import { NativePlayer } from "./NativePlayer";
import { MediaTrack } from "../types/MediaTrack";
import { MediaTrackType } from "../types/MediaTrackType";

class FakeTextTrackList extends Array<TextTrack> implements TextTrackList {
    private eventTarget: EventTarget = new EventTarget();

    onaddtrack: (this: TextTrackList, ev: TrackEvent) => unknown;
    onchange: (this: TextTrackList, ev: Event) => unknown;
    onremovetrack: (this: TextTrackList, ev: TrackEvent) => unknown;

    getTrackById(): TextTrack | null {
        throw new Error("Method not implemented.");
    }

    addEventListener(type: string, listener: EventListener, options?: unknown) {
        this.eventTarget.addEventListener(type, listener, options);
    }

    removeEventListener(type: string, listener: EventListener, options?: unknown): void {
        this.eventTarget.removeEventListener(type, listener, options);
    }

    dispatchEvent(event: Event): boolean {
        return this.eventTarget.dispatchEvent(event);
    }

    clear() {
        while(this.length) {
            this.shift();
        }
    }
}

describe('NativePlayer', () => {
    const mpdSource = 'http://example.local/manifest.mpd';
    const logEvent = vi.fn();
    const tracksChanged = vi.fn();
    const textEnabled = false;
    const textLanguage = "";
    const videoElement = mock<HTMLVideoElement>({
        textTracks: new FakeTextTrackList(),
    });
    let eventTarget: EventTarget;

    beforeEach(() => {
        eventTarget = new EventTarget();
        videoElement.addEventListener.mockImplementation((evName: string, fn: () => void) => {
            eventTarget.addEventListener(evName, fn as EventListener);
        });
        videoElement.removeEventListener.mockImplementation((evName: string, fn: () => void) => {
            eventTarget.removeEventListener(evName, fn as EventListener);
        });
        videoElement.dispatchEvent.mockImplementation((ev: Event) => {
            return eventTarget.dispatchEvent(ev);
        });
        (videoElement.textTracks as FakeTextTrackList).clear();
    });

    afterEach(() => {
        vi.clearAllMocks();
        mockReset(videoElement);
    });

    test('can create NativePlayer', async () => {
        const player = new NativePlayer({
            logEvent,
            tracksChanged,
            videoElement,
            textEnabled,
            textLanguage,
         });
        await player.initialize(mpdSource);
        player.setSubtitlesElement(mock<HTMLDivElement>());
        expect(videoElement.addEventListener).not.toHaveBeenCalled();
        expect(videoElement.src).toEqual(mpdSource);
        player.destroy();
    });

    test('can auto play', async () => {
        const player = new NativePlayer({
            logEvent,
            tracksChanged,
            videoElement,
            textEnabled,
            textLanguage,
            autoplay: true
        });
        await player.initialize(mpdSource);
        expect(videoElement.addEventListener).toHaveBeenCalledWith('canplay', expect.any(Function));
        const playProm = new Promise<void>((resolve) => {
            videoElement.play.mockImplementationOnce(async () => {
                resolve();
            });
        });
        const ev = new Event('canplay');
        Object.defineProperty(ev, 'target', { value: videoElement });
        videoElement.dispatchEvent(ev);
        await playProm;
        expect(videoElement.play).toHaveBeenCalledTimes(1);
        player.destroy();
    });

    test('can set text track', async () => {
        const mediaTrack: MediaTrack = {
            id: '1',
            trackType: MediaTrackType.TEXT,
            active: false,
        };
        const textTrack1 = mock<TextTrack>({
            id: '1',
            mode: 'disabled',
        });
        const textTrack2 = mock<TextTrack>({
            id: '2',
            mode: 'showing',
        });
        (videoElement.textTracks as FakeTextTrackList).push(textTrack1);
        (videoElement.textTracks as FakeTextTrackList).push(textTrack2);
        const player = new NativePlayer({
            logEvent,
            tracksChanged,
            videoElement,
            textEnabled,
            textLanguage,
            autoplay: false,
        });
        await player.initialize(mpdSource);
        player.setTextTrack(mediaTrack);
        expect(textTrack1.mode).toEqual('showing');
        expect(textTrack2.mode).toEqual('disabled');
    });

    test('can disable all text tracks', async () => {
        const textTrack1 = mock<TextTrack>({
            id: '1',
            mode: 'disabled',
        });
        const textTrack2 = mock<TextTrack>({
            id: '2',
            mode: 'showing',
        });
        (videoElement.textTracks as FakeTextTrackList).push(textTrack1);
        (videoElement.textTracks as FakeTextTrackList).push(textTrack2);
        const player = new NativePlayer({
            logEvent,
            tracksChanged,
            videoElement,
            textEnabled,
            textLanguage,
            autoplay: false,
        });
        await player.initialize(mpdSource);
        player.setTextTrack(null);
        expect(textTrack1.mode).toEqual('disabled');
        expect(textTrack2.mode).toEqual('disabled');
    });
});