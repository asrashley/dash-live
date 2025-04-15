import { vi, describe, test, expect, beforeEach, afterEach } from "vitest";
import { importLibrary } from "./importLibrary";
import { DashJsPlayer } from "./DashJsPlayer";
import { mock, mockClear } from "vitest-mock-extended";
import { MediaPlayerClass, MediaPlayerFactory } from "dashjs";

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
    const mockMediaPlayerFactory = mock<MediaPlayerFactory>();
    const mockMediaPlayer = mock<MediaPlayerClass>();

    beforeEach(() => {
        mockMediaPlayerFactory.create.mockReturnValue(mockMediaPlayer);
        mockedImportLibrary.mockImplementationOnce(async () => {
            (window as WindowWithDashJs)["dashjs"] = {
                MediaPlayer: vi.fn().mockReturnValue(mockMediaPlayerFactory),
            };
        });
    });

    afterEach(() => {
        vi.clearAllMocks();
        mockClear(mockMediaPlayerFactory);
    });

    test.each(DashJsPlayer.LOCAL_VERSIONS)('can use dash.js version %s', async (version: string) => {
        const jsUrl = DashJsPlayer.cdnTemplate(version);
        const videoElement = document.createElement('video');
        const addEventSpy = vi.spyOn(videoElement, 'addEventListener');
        const player = new DashJsPlayer({ logEvent, version, videoElement });
        await player.initialize(mpdSource);
        expect(mockedImportLibrary).toHaveBeenCalledWith(jsUrl);
        expect(mockMediaPlayerFactory.create).toHaveBeenCalledTimes(1);
        expect(mockMediaPlayer.initialize).toHaveBeenCalledWith(videoElement, mpdSource, false);
        expect(addEventSpy).not.toHaveBeenCalled();
        player.destroy();
        expect(mockMediaPlayer.destroy).toHaveBeenCalledTimes(1);
    });

    test('can use an alternate dash.js version', () => {
        expect(DashJsPlayer.cdnTemplate('1.2.3')).toEqual('https://cdn.dashjs.org/1.2.3/dash.all.min.js');
    });

    test('can auto play', async () => {
        const videoElement = document.createElement('video');
        const addEventSpy = vi.spyOn(videoElement, 'addEventListener');
        const player = new DashJsPlayer({ logEvent, videoElement, autoplay: true, version: DashJsPlayer.LOCAL_VERSIONS[0],  });
        await player.initialize(mpdSource);
        expect(mockMediaPlayer.initialize).toHaveBeenCalledWith(videoElement, mpdSource, true);
        expect(addEventSpy).toHaveBeenCalledWith('canplay', expect.any(Function));
        player.destroy();
    });
});