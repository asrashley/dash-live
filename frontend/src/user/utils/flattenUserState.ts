import { FlattenedUserState } from "../types/FlattenedUserState";
import { InitialUserState } from "../types/InitialUserState";

export function flattenUserState({ groups, ...user }: InitialUserState): FlattenedUserState {
    const flat: FlattenedUserState = {
        ...user,
        adminGroup: groups.includes('ADMIN'),
        mediaGroup: groups.includes('MEDIA'),
        userGroup: groups.includes('USER'),
    };
    return flat;
}
