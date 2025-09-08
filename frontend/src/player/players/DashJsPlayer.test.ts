import { vi, describe, test, expect, beforeEach, afterEach } from "vitest";
import { mock, mockReset } from "vitest-mock-extended";
import type { MediaInfo, MediaPlayerClass, MediaPlayerFactory, PeriodSwitchEvent } from "dashjs";
import { importLibrary } from "./importLibrary";
import { DashJsPlayer, mediaInfoToMediaTrack, mediaTrackType } from "./DashJsPlayer";
import { MediaTrack } from "../types/MediaTrack";
import { MediaTrackType } from "../types/MediaTrackType";

vi.mock("./importLibrary", () => {
    return {
        importLibrary: vi.fn(),
    };
});

interface WindowWithDashJs extends Window {
    dashjs: {
        MediaPlayer: () => MediaPlayerFactory;
    };
}

describe('DashJsPlayer', () => {
    const mpdSource = 'http://example.local/manifest.mpd';
    const mockedImportLibrary = vi.mocked(importLibrary);
    const logEvent = vi.fn();
    const tracksChanged = vi.fn();
    const mockMediaPlayerFactory = mock<MediaPlayerFactory>();
    const mockMediaPlayer = mock<MediaPlayerClass>();
    const videoElement = mock<HTMLVideoElement>();
    const videoMediaInfo = mock<MediaInfo>({
        id: "v1",
        index: 0,
        isText: false,
        type: "video",
    });
    const audioMediaInfo = mock<MediaInfo>({
        id: "a1",
        index: 1,
        isText: false,
        lang: "eng",
        type: "audio",
    });
    const textMediaInfo = mock<MediaInfo>({
        id: "t1",
        index: 2,
        isText: true,
        lang: "eng",
        type: "text",
    });
    let textTrack: MediaTrack;

    beforeEach(() => {
        textTrack = {
            id: textMediaInfo.id,
            trackType: MediaTrackType.TEXT,
            language: textMediaInfo.lang || "",
            active: false,
        };
        mockMediaPlayerFactory.create.mockReturnValue(mockMediaPlayer);
        mockedImportLibrary.mockImplementationOnce(async () => {
            const MediaPlayer = vi.fn().mockReturnValue(mockMediaPlayerFactory);
            Object.defineProperty(MediaPlayer, 'events', {
                value: {
                    PERIOD_SWITCH_COMPLETED: 'periodSwitchCompleted',
                }
            });
            (window as WindowWithDashJs)["dashjs"] = {
                MediaPlayer,
            };
        });
        mockMediaPlayer.getCurrentTrackFor.mockImplementation((type: MediaInfo["type"]) => {
            switch (type) {
                case 'video': return videoMediaInfo;
                case 'audio': return audioMediaInfo;
                case 'text': return textMediaInfo;
                default: return null;
            }
        });
        mockMediaPlayer.getCurrentTextTrackIndex.mockImplementation(() => textTrack.active ? textMediaInfo.index : -1);
        mockMediaPlayer.getTracksFor.mockImplementation((type: MediaInfo["type"]) => {
            switch (type) {
                case 'video': return [videoMediaInfo];
                case 'audio': return [audioMediaInfo];
                case 'text': return [textMediaInfo];
                default: return [];
            }
        });
    });

    afterEach(() => {
        vi.clearAllMocks();
        mockReset(mockMediaPlayerFactory);
        mockReset(mockMediaPlayer);
        mockReset(videoElement);
    });

    test.each(DashJsPlayer.LOCAL_VERSIONS)('can use dash.js version %s', async (version: string) => {
        const jsUrl = DashJsPlayer.cdnTemplate(version);
        const player = new DashJsPlayer({
            logEvent,
            version,
            videoElement,
            tracksChanged,
            textEnabled: false,
            textLanguage: "",
        });
        await player.initialize(mpdSource);
        expect(mockedImportLibrary).toHaveBeenCalledWith(jsUrl);
        expect(mockMediaPlayerFactory.create).toHaveBeenCalledTimes(1);
        expect(mockMediaPlayer.initialize).toHaveBeenCalledWith(videoElement, mpdSource, false);
        expect(videoElement.addEventListener).not.toHaveBeenCalled();
        player.destroy();
        expect(mockMediaPlayer.destroy).toHaveBeenCalledTimes(1);
    });

    test('can use an alternate dash.js version', () => {
        expect(DashJsPlayer.cdnTemplate('1.2.3')).toEqual('https://cdn.dashjs.org/1.2.3/dash.all.min.js');
    });

    test('can auto play', async () => {
        const player = new DashJsPlayer({
            logEvent,
            videoElement,
            tracksChanged,
            textEnabled: false,
            textLanguage: "",
            autoplay: true,
        });
        await player.initialize(mpdSource);
        expect(mockMediaPlayer.initialize).toHaveBeenCalledWith(videoElement, mpdSource, true);
        expect(videoElement.addEventListener).toHaveBeenCalledWith(
            'canplay', expect.any(Function), { signal: expect.any(AbortSignal) });
        player.destroy();
    });

    test('can set subtitles element before initialize', async () => {
        const subsElt = document.createElement('div');
        const player = new DashJsPlayer({
            logEvent,
            tracksChanged,
            videoElement,
            autoplay: true,
            version: DashJsPlayer.LOCAL_VERSIONS[0],
            textEnabled: true,
            textLanguage: "eng",
        });
        player.setSubtitlesElement(subsElt);
        await player.initialize(mpdSource);
        expect(mockMediaPlayer.attachTTMLRenderingDiv).toHaveBeenCalledTimes(1);
        expect(mockMediaPlayer.attachTTMLRenderingDiv).toHaveBeenCalledWith(subsElt);
    });

    test('can set subtitles element after initialize', async () => {
        const subsElt = document.createElement('div');
        const player = new DashJsPlayer({
            logEvent,
            tracksChanged,
            videoElement,
            autoplay: true,
            version: DashJsPlayer.LOCAL_VERSIONS[0],
            textEnabled: true,
            textLanguage: "eng",
        });
        await player.initialize(mpdSource);
        expect(mockMediaPlayer.attachTTMLRenderingDiv).not.toHaveBeenCalled();
        player.setSubtitlesElement(subsElt);
        expect(mockMediaPlayer.attachTTMLRenderingDiv).toHaveBeenCalledTimes(1);
        expect(mockMediaPlayer.attachTTMLRenderingDiv).toHaveBeenCalledWith(subsElt);
    });

    test('can change text tracks', async () => {
        mockMediaPlayer.getTracksFor.mockReturnValue([textMediaInfo])
        const player = new DashJsPlayer({
            logEvent,
            videoElement,
            tracksChanged,
            textEnabled: false,
            textLanguage: "",
            autoplay: true,
        });
        await player.initialize(mpdSource);
        player.setTextTrack(null);
        expect(mockMediaPlayer.setTextTrack).toHaveBeenCalledTimes(1);
        expect(mockMediaPlayer.setTextTrack).toHaveBeenLastCalledWith(-1);
        player.setTextTrack(textTrack);
        expect(mockMediaPlayer.setTextTrack).toHaveBeenCalledTimes(2);
        expect(mockMediaPlayer.setTextTrack).toHaveBeenLastCalledWith(0);
        player.destroy();
    });

    test('setting text track after destroy does nothing', async () => {
        const player = new DashJsPlayer({
            logEvent,
            videoElement,
            tracksChanged,
            textEnabled: false,
            textLanguage: "",
            autoplay: true,
        });
        await player.initialize(mpdSource);
        player.destroy();
        player.setTextTrack(null);
    });

    test('calls setTracks when track list changes', async () => {
        const player = new DashJsPlayer({
            logEvent,
            videoElement,
            tracksChanged,
            textEnabled: false,
            textLanguage: "",
            autoplay: true,
        });
        await player.initialize(mpdSource);
        expect(mockMediaPlayer.on).toHaveBeenCalledWith('periodSwitchCompleted', expect.any(Function));
        const periodSwitchHandler = mockMediaPlayer.on.mock.calls.find((call => call[0] === 'periodSwitchCompleted'))?.[1];
        expect(periodSwitchHandler).toBeDefined();
        expect(tracksChanged).not.toHaveBeenCalled();
        const ev = mock<PeriodSwitchEvent>();
        periodSwitchHandler?.(ev);
        expect(tracksChanged).toHaveBeenCalledTimes(1);
        const expectedTracks: MediaTrack[] = [videoMediaInfo, audioMediaInfo, textMediaInfo].map(mi=> {
            const current: MediaInfo | null = mi.type === 'text' ? null : mi;
            return mediaInfoToMediaTrack(mi, current);
        });
        expect(expectedTracks[2].active).toEqual(false);
        expect(tracksChanged).toHaveBeenLastCalledWith(expectedTracks);
        textTrack.active = true;
        periodSwitchHandler?.(ev);
        expect(tracksChanged).toHaveBeenCalledTimes(2);
        expectedTracks[2].active = true;
        expect(tracksChanged).toHaveBeenLastCalledWith(expectedTracks);
        player.destroy();
    });

    test('period switch event after destroy', async () => {
        const player = new DashJsPlayer({
            logEvent,
            videoElement,
            tracksChanged,
            textEnabled: false,
            textLanguage: "",
            autoplay: true,
        });
        await player.initialize(mpdSource);
        expect(mockMediaPlayer.on).toHaveBeenCalledWith('periodSwitchCompleted', expect.any(Function));
        const periodSwitchHandler = mockMediaPlayer.on.mock.calls.find((call => call[0] === 'periodSwitchCompleted'))?.[1];
        expect(periodSwitchHandler).toBeDefined();
        player.destroy();
        const ev = mock<PeriodSwitchEvent>();
        periodSwitchHandler?.(ev);
    });

    test.each([
        ['video', MediaTrackType.VIDEO],
        ['audio', MediaTrackType.AUDIO],
        ['text', MediaTrackType.TEXT],
        ['image', MediaTrackType.IMAGE]
    ])('mediaTrackType %s => %s', (tt: MediaInfo["type"], expected: MediaTrackType) => {
        expect(mediaTrackType(tt)).toEqual(expected);
    });

    test('unknown mediaInfo type', () => {
        expect(mediaTrackType('unknown' as MediaInfo["type"])).toEqual(MediaTrackType.UNKNOWN);
    });
});