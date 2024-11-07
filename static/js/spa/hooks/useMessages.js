import { signal, useComputed } from "@preact/signals";

const messages = signal({ alerts: [], nextId: 1 });

const appendMessage = (text, level = "warning") => {
  const id = messages.value.nextId;
  const alerts = [
    ...messages.value.alerts,
    {
      text,
      id,
      level,
    },
  ];
  messages.value = {
    nextId: id + 1,
    alerts,
  };
};

const removeAlert = (id) => {
  const alerts = messages.value.alerts.filter((a) => a.id !== id);
  messages.value = { ...messages.value, alerts };
};

export function useMessages() {
  const alerts = useComputed(() => {
    return messages.value.alerts;
  });

  return { alerts, appendMessage, removeAlert };
}
