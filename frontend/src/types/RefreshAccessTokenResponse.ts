import { CsrfTokenCollection } from "./CsrfTokenCollection";
import { JwtToken } from "./JwtToken";

export interface RefreshAccessTokenResponse {
    accessToken: JwtToken;
    csrfTokens: CsrfTokenCollection;
}