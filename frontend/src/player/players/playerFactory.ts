import { AbstractDashPlayer, DashPlayerProps } from "../types/AbstractDashPlayer";
import { DashPlayerTypes } from "../types/DashPlayerTypes";
import { DashJsPlayer } from "./DashJsPlayer";
import { NativePlayer } from "./NativePlayer";
import { ShakaPlayer } from "./ShakaPlayer";

export function playerFactory(playerType: DashPlayerTypes, props: DashPlayerProps): AbstractDashPlayer {
    switch (playerType) {
        case 'dashjs':
            return new DashJsPlayer(props);
        case 'native':
            return new NativePlayer(props);
        case 'shaka':
            return new ShakaPlayer(props);
    }
}