import { createContext } from 'preact';
import { signal, computed, type Signal, type ReadonlySignal } from "@preact/signals";
import { DialogState } from './types/DialogState';
import { InitialUserState, UserState } from './types/UserState';

export interface AppStateType {
  backdrop: ReadonlySignal<boolean>;
  dialog: Signal<DialogState>;
  user: ReadonlySignal<UserState>;
  setUser: (ius: InitialUserState) => void;
}

export const AppStateContext = createContext<AppStateType>(null);

export interface CreateAppStateProps {
  userInfo: InitialUserState
}

export function createAppState(userInfo: InitialUserState = {isAuthenticated: false, groups:[]}): AppStateType {
  const dialog = signal(null);
  const userData = signal<InitialUserState>(userInfo);
  const user = computed<UserState>(() => ({
    ...userData.value,
    permissions: {
      admin: userData.value.groups.includes('ADMIN'),
      media: userData.value.groups.includes('MEDIA'),
      user: userData.value.groups.includes('USER'),
    },
  }));

  const backdrop = computed(() => {
    return dialog.value?.backdrop === true;
  });

  const setUser = (ius: InitialUserState) => {
    userData.value = {...ius};
  };

  return { dialog, backdrop, user, setUser };
}
