import { CsrfTokenCollection } from "../../types/CsrfTokenCollection";
import { JWToken } from "./JWToken";

export interface RefreshAccessTokenResponse {
    accessToken: JWToken;
    csrfTokens: CsrfTokenCollection;
}