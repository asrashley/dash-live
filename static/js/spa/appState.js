import { createContext } from 'preact';
import { signal, computed } from "@preact/signals";

export const AppStateContext = createContext();

export function createAppState(userInfo = {groups:[]}) {
  const dialog = signal(null);
  const user = signal({
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

