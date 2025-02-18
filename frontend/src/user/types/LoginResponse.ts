import { JWToken } from "./JWToken";
import { InitialUserState } from "./InitialUserState";

export interface LoginResponse {
    success: boolean;
    error?: string;
    csrf_token: string;
    accessToken?: JWToken;
    refreshToken?: JWToken;
    user?: InitialUserState
}
