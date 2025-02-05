import { FlattenedUserState } from "../../types/FlattenedUserState";
import { UserState } from "../../types/UserState";

export function flattenUserState({ groups, ...user }: UserState): FlattenedUserState {
    const flat: FlattenedUserState = {
        ...user,
        adminGroup: groups.includes('ADMIN'),
        mediaGroup: groups.includes('MEDIA'),
        userGroup: groups.includes('USER'),
    };
    return flat;
}
