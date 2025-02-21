import { AdaptationSetJson } from "./AdaptationSetJson"

export type PeriodJson = {
    adaptationSets: AdaptationSetJson[];
    event_streams: object[],
    id: string;
    start: string;
};