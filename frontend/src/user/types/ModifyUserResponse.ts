import type { InitialUserState } from "./InitialUserState";

export interface ModifyUserResponse {
    success: boolean;
    errors: string[];
    user?: InitialUserState;
}
