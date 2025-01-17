import { CsrfTokenCollection } from "./CsrfTokenCollection";
import { JWToken } from "./JWToken";

export interface InitialApiTokens {
    csrfTokens: Partial<CsrfTokenCollection>;
    accessToken: JWToken | null;
    refreshToken: JWToken | null;
}
