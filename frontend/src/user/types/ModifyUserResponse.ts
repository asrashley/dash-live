import { InitialUserState } from "./UserState";

export interface ModifyUserResponse {
    success: boolean;
    errors: string[];
    user?: InitialUserState;
}
