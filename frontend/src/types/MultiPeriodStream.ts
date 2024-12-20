import { CsrfTokenCollection } from "./CsrfTokenCollection";
import { MpsPeriod } from "./MpsPeriod";

export type MultiPeriodStream = {
    pk: number | null;
    name: string;
    title: string;
    options: object | null;
    periods: MpsPeriod[];
};

export type MultiPeriodStreamJson = {
    csrfTokens: CsrfTokenCollection;
    model: MultiPeriodStream;
};