import { CsrfTokenCollection } from "./CsrfTokenCollection";
import { MultiPeriodStream } from "./MultiPeriodStream";

export interface ModifyMultiPeriodStreamJson {
    csrfTokens: Partial<CsrfTokenCollection>;
    errors: string[];
    success: boolean;
    model: MultiPeriodStream;
}