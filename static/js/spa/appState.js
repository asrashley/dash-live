import { createContext } from 'preact';
import { signal, computed } from "@preact/signals";

export const AppStateContext = createContext();

export function createAppState(userInfo = {groups:[]}) {
  const messages = signal({alerts: [], nextId: 1});
  const dialog = signal(null);
  const user = signal({
    ...userInfo,
    permissions: {
      admin: userInfo.groups.includes('ADMIN'),
      media: userInfo.groups.includes('MEDIA'),
      user: userInfo.groups.includes('USER'),
    },
  });

  const alerts = computed(() => {
    return messages.value?.alerts ?? [];
  });

  const backdrop = computed(() => {
    return dialog.value?.backdrop === true;
  });

  return { dialog, messages, alerts, backdrop, user };
}

export function appendMessage(messageSignal, text, level='warning') {
  const id = messageSignal.value?.nextId ?? 1;
  const alerts = [
    ...messageSignal.value?.alerts ?? [],
    {
      text,
      id,
      level,
    },
  ];
  messageSignal.value = {
    nextId: id + 1,
    alerts,
  };
}
