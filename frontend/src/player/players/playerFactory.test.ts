import { describe, expect, test, vi } from "vitest";
import { DashPlayerTypes } from "../types/DashPlayerTypes";
import { playerFactory } from "./playerFactory";
import { DashPlayerProps } from "./AbstractDashPlayer";

describe('playerFactory', () => {
    const logEvent = vi.fn();
    const tracksChanged = vi.fn();

    test.each(['dashjs', 'native', 'shaka'])('creates player of type %s', (playerType: DashPlayerTypes) => {
        const videoElement = document.createElement('video');

        const props: DashPlayerProps = {
            logEvent,
            videoElement,
            tracksChanged,
            textLanguage: "",
            textEnabled: false,
        };
        const player = playerFactory(playerType, props);
        expect(player).toBeDefined();
    });
});