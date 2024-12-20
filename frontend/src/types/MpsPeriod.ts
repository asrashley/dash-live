import { MpsTrack } from './MpsTrack';

export type MpsPeriod = {
    duration: string;
    ordering: number;
    parent: number;
    pid: string;
    pk: number | string;
    start: string;
    stream: number;
    tracks: MpsTrack[];
    new?: boolean;
};
