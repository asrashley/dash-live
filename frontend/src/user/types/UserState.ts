import { InitialUserState } from "./InitialUserState";

export type UserState = InitialUserState & {
    isAuthenticated: boolean;
    permissions: {
        admin: boolean,
        media: boolean,
        user: boolean,
    }
}