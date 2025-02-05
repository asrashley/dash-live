import { EditUserState } from "../../types/EditUserState";
import { InitialUserState } from "../../types/UserState";
import { UserValidationErrors } from "../../hooks/useAllUsers";

export function validateUserState(user: EditUserState, allUsers: InitialUserState[] = []): UserValidationErrors {
    const errs: UserValidationErrors = {};
    if (user.pk) {
      if (allUsers.some(({ pk, username }) => pk !== user.pk && username === user.username)) {
        errs.username = `${user.username} already exists`;
      }
    } else {
      if (allUsers.some(({ username }) => username === user.username)) {
        errs.username = `${user.username} username already exists`;
      }
      if (!user.password) {
        errs.password = 'a password is required';
      } else if (user.password !== user.confirmPassword) {
        errs.password = 'passwords do not match';
      }
      if (allUsers.some(({ email }) => email === user.email)) {
        errs.email = `${user.email} email address already exists`;
      }
    }
    if (!user.username) {
      errs.username = 'a username is required';
    }
    if (!user.email) {
      errs.email = 'an email address is required';
    }
    return errs;
  }
