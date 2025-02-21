import type { OptionMapWithChildren } from "@dashlive/options";
import type { PeriodJson } from "./PeriodsJson";

export interface DashParameters {
    dash: {
        locationURL: string;
        mediaDuration: string;
        minBufferTime: string;
        mpd_id: string;
        now: string;
        periods: PeriodJson[];
        profiles: string[];
        publishTime: string;
        startNumber: number;
        suggestedPresentationDelay: number;
        timeSource: null;
        title: string;
    },
    options: OptionMapWithChildren;
    url: string;
}
