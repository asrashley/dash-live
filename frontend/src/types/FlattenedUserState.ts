import { InitialUserState } from "../types/UserState";


export type FlattenedUserState = Omit<InitialUserState, 'groups'> & {
  adminGroup: boolean;
  mediaGroup: boolean;
  userGroup: boolean;
};
