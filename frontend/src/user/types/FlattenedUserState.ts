import type { InitialUserState } from "../types/InitialUserState";


export type FlattenedUserState = Omit<InitialUserState, 'groups'> & {
  adminGroup: boolean;
  mediaGroup: boolean;
  userGroup: boolean;
};
