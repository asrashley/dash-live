import { JwtToken } from "./JwtToken";
import { InitialUserState } from "./UserState";

export interface LoginResponse {
    success: boolean;
    error?: string;
    mustChange?: boolean;
    csrf_token: string;
    accessToken?: JwtToken;
    refreshToken?: JwtToken;
    user?: InitialUserState
}
