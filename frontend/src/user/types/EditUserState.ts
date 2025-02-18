import { FlattenedUserState } from "./FlattenedUserState";


export type EditUserState = FlattenedUserState & {
  password?: string;
  confirmPassword?: string;
};
