import { createContext } from 'preact';
import { signal, computed } from "@preact/signals";

export const AppStateContext = createContext();

export function createAppState() {
  const messages = signal({alerts: [], nextId: 1});
  const dialog = signal(null);

  const alerts = computed(() => {
    return messages.value?.alerts ?? [];
  });

  const backdrop = computed(() => {
    return dialog.value?.backdrop === true;
  });

  return { dialog, messages, alerts, backdrop };
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
