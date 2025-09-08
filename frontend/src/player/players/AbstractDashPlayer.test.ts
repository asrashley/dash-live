import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { mock, mockReset } from "vitest-mock-extended";
import { AbstractDashPlayer, DashPlayerProps } from "./AbstractDashPlayer";
import { MediaTrack } from "../types/MediaTrack";
import { OptionMapWithChildren } from "@dashlive/options";
import { KeyParameters } from "../types/KeyParameters";
import { MediaTrackType } from "../types/MediaTrackType";

class DUT extends AbstractDashPlayer {
    public mpd?: string;
    public options?: OptionMapWithChildren;
    public keys?: Map<string, KeyParameters>;

    async initialize(mpd: string, options: OptionMapWithChildren, keys: Map<string, KeyParameters>): Promise<void> {
        this.props.videoElement.addEventListener('canplay', this.onCanPlayEvent);
        this.mpd = mpd;
        this.options = options;
        this.keys = keys;
    }

    destroy() {
    }

    setTextTrack(_track: MediaTrack | null): void {
        throw new Error("Method not implemented.");
    }

    callMaybeTracksChanged(tracks: MediaTrack[]) {
        this.maybeTracksChanged(tracks);
    }
}

describe('AbstractDashPlayer', () => {
    const videoElement = mock<HTMLVideoElement>();
    const props: DashPlayerProps = {
        videoElement,
        textLanguage: "",
        textEnabled: false,
        logEvent: vi.fn(),
        tracksChanged: vi.fn(),
    };
    const keys: Map<string, KeyParameters> = new Map();
    const mpdUrl = 'http://example.local/manifest.mpd';
    let eventTarget: EventTarget;

    beforeEach(() => {
        keys.clear();
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
    });

    afterEach(() => {
        vi.clearAllMocks();
        mockReset(videoElement);
    });

    test('plays using autoplay', async () => {
        const playProm = new Promise<void>((resolve) => {
            videoElement.play.mockImplementationOnce(async () => {
                resolve();
            });
        });
        videoElement.muted = false;
        const player = new DUT(props);
        await player.initialize(mpdUrl, {}, keys);
        expect(videoElement.play).not.toHaveBeenCalled();
        expect(videoElement.addEventListener).toHaveBeenCalledWith('canplay', expect.any(Function));
        const ev = new Event('canplay');
        Object.defineProperty(ev, 'target', { value: videoElement });
        videoElement.dispatchEvent(ev);
        await playProm;
        expect(videoElement.play).toHaveBeenCalledTimes(1);
        expect(videoElement.muted).toEqual(false);
    });

    test('plays using mute if browser blocks autoplay', async () => {
        videoElement.play.mockRejectedValueOnce(new Error('Autoplay is blocked'));
        const playProm = new Promise<void>((resolve) => {
            videoElement.play.mockImplementationOnce(async () => {
                resolve();
            });
        });
        videoElement.muted = false;
        const player = new DUT(props);
        await player.initialize(mpdUrl, {}, keys);
        expect(videoElement.play).not.toHaveBeenCalled();
        expect(videoElement.addEventListener).toHaveBeenCalledWith('canplay', expect.any(Function));
        const ev = new Event('canplay');
        Object.defineProperty(ev, 'target', { value: videoElement });
        videoElement.dispatchEvent(ev);
        await playProm;
        expect(videoElement.play).toHaveBeenCalledTimes(2);
        expect(videoElement.muted).toBe(true);
    });

    test('maybeTracksChanged calls tracksChanged from initial empty list', async () => {
        videoElement.play.mockResolvedValue();
        const player = new DUT(props);
        await player.initialize(mpdUrl, {}, keys);
        const tracks: MediaTrack[] = [{
            id: '1',
            trackType: MediaTrackType.VIDEO,
            active: true,
        }];
        player.callMaybeTracksChanged(tracks);
        expect(props.tracksChanged).toHaveBeenCalledTimes(1);
        expect(props.tracksChanged).toHaveBeenCalledWith(tracks);
    });

    test.each<[string, Partial<MediaTrack>]>([
        ['id', { id: '3' }],
        ['active', { active: false }],
        ['language', { language: 'fra' }],
    ])('maybeTracksChanged calls tracksChanged when %s changes', async (_title: string, changes: Partial<MediaTrack>) => {
        videoElement.play.mockResolvedValue();
        const player = new DUT(props);
        await player.initialize(mpdUrl, {}, keys);
        const tracks: MediaTrack[] = [{
            id: '1',
            trackType: MediaTrackType.VIDEO,
            active: true,
        }, {
            id: '2',
            trackType: MediaTrackType.AUDIO,
            language: 'eng',
            active: true,
        }];
        player.callMaybeTracksChanged(tracks);
        expect(props.tracksChanged).toHaveBeenCalledTimes(1);
        expect(props.tracksChanged).toHaveBeenCalledWith([...tracks]);
        player.callMaybeTracksChanged(tracks);
        expect(props.tracksChanged).toHaveBeenCalledTimes(1);
        const newTracks: MediaTrack[] = [
            tracks[0],
            {
                ...tracks[1],
                ...changes,
            },
        ];
        player.callMaybeTracksChanged(newTracks);
        expect(props.tracksChanged).toHaveBeenCalledTimes(2);
    });

    test('maybeTracksChanged calls tracksChanged when track added', async () => {
        videoElement.play.mockResolvedValue();
        const player = new DUT(props);
        await player.initialize(mpdUrl, {}, keys);
        const tracks: MediaTrack[] = [{
            id: '1',
            trackType: MediaTrackType.VIDEO,
            active: true,
        }];
        player.callMaybeTracksChanged(tracks);
        expect(props.tracksChanged).toHaveBeenCalledTimes(1);
        expect(props.tracksChanged).toHaveBeenCalledWith([...tracks]);
        player.callMaybeTracksChanged(tracks);
        expect(props.tracksChanged).toHaveBeenCalledTimes(1);
        const newTracks: MediaTrack[] = [
            tracks[0],
            {
                id: '2',
                trackType: MediaTrackType.AUDIO,
                active: true,
            }
        ];
        player.callMaybeTracksChanged(newTracks);
        expect(props.tracksChanged).toHaveBeenCalledTimes(2);
    });

    test('maybeTracksChanged calls tracksChanged when track removed', async () => {
        videoElement.play.mockResolvedValue();
        const player = new DUT(props);
        await player.initialize(mpdUrl, {}, keys);
        const tracks: MediaTrack[] = [{
            id: '1',
            trackType: MediaTrackType.VIDEO,
            active: true,
        }, {
            id: '2',
            trackType: MediaTrackType.AUDIO,
            active: true,
        }
        ];
        player.callMaybeTracksChanged(tracks);
        expect(props.tracksChanged).toHaveBeenCalledTimes(1);
        expect(props.tracksChanged).toHaveBeenCalledWith([...tracks]);
        player.callMaybeTracksChanged(tracks);
        expect(props.tracksChanged).toHaveBeenCalledTimes(1);
        const newTracks: MediaTrack[] = [
            tracks[0],
        ];
        player.callMaybeTracksChanged(newTracks);
        expect(props.tracksChanged).toHaveBeenCalledTimes(2);
    });
});