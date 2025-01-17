import { CsrfTokenCollection } from "./CsrfTokenCollection";
import { MultiPeriodStream } from "./MultiPeriodStream";

export interface ModifyMultiPeriodStreamResponse {
    errors: string[];
    success: boolean;
    model: MultiPeriodStream;
}

export interface ModifyMultiPeriodStreamJson extends ModifyMultiPeriodStreamResponse {
    csrfTokens: Partial<CsrfTokenCollection>;
}