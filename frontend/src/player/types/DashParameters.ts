import type { OptionsContainerType } from "@dashlive/dash-options";
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
    options: OptionsContainerType;
    url: string;
}
