import { CsrfTokenCollection } from "./CsrfTokenCollection";

export type MultiPeriodStreamSummary = {
    duration: string;
    name: string;
    options: object;
    periods: number[];
    pk: number;
    title: string;
};

export type AllMultiPeriodStreamsJson = {
    csrfTokens: CsrfTokenCollection;
    streams: MultiPeriodStreamSummary[];
};
