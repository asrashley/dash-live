import { MpsPeriod } from "./MpsPeriod";
import { MultiPeriodStream } from "./MultiPeriodStream";


export type DecoratedMultiPeriodStream = Omit<MultiPeriodStream, 'periods'> & {
    periods: MpsPeriod[];
    modified: boolean;
    lastModified: number;
};
