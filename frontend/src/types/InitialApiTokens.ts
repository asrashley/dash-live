import { CsrfTokenCollection } from "./CsrfTokenCollection";
import { JwtToken } from "./JwtToken";

export interface InitialApiTokens {
    csrfTokens: Partial<CsrfTokenCollection>;
    accessToken: JwtToken | null;
    refreshToken: JwtToken | null;
}
