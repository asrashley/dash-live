import { JWToken } from "./JWToken";
import { InitialUserState } from "./UserState";

export interface LoginResponse {
    success: boolean;
    error?: string;
    mustChange?: boolean;
    csrf_token: string;
    accessToken?: JWToken;
    refreshToken?: JWToken;
    user?: InitialUserState
}
