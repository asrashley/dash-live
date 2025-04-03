import { describe, expect, test, vi } from "vitest";
import { DashPlayerTypes } from "../types/DashPlayerTypes";
import { playerFactory } from "./playerFactory";
import { DashPlayerProps } from "../types/AbstractDashPlayer";

describe('playerFactory', () => {
    const logEvent = vi.fn();

    test.each(['dashjs', 'native', 'shaka'])('creates player of type %s', (playerType: DashPlayerTypes) => {
        const videoElement = document.createElement('video');

        const props: DashPlayerProps = {
            logEvent,
            videoElement,
        };
        const player = playerFactory(playerType, props);
        expect(player).toBeDefined();
    });
});