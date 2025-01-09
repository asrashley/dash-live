import { createContext } from 'preact';
import { signal, computed, type Signal, type ReadonlySignal } from "@preact/signals";
import { DialogState } from './types/DialogState';
import { InitialUserState, UserState } from './types/UserState';

export interface AppStateType {
  backdrop: ReadonlySignal<boolean>;
  dialog: Signal<DialogState>;
  user: Signal<UserState>;
}

export const AppStateContext = createContext<AppStateType>(null);

export interface CreateAppStateProps {
  userInfo: InitialUserState
}

export function createAppState(userInfo: InitialUserState = {isAuthenticated: false, groups:[]}): AppStateType {
  const dialog = signal(null);
  const user = signal<UserState>({
    ...userInfo,
    permissions: {
      admin: userInfo.groups.includes('ADMIN'),
      media: userInfo.groups.includes('MEDIA'),
      user: userInfo.groups.includes('USER'),
    },
  });

  const backdrop = computed(() => {
    return dialog.value?.backdrop === true;
  });

  return { dialog, backdrop, user };
}
