import { type Signal, signal, useComputed } from "@preact/signals";
import { MessageLevel, MessageType } from "../types/MessageType";

type MessagesState = {
  alerts: MessageType[];
  nextId: number;
}

const messages = signal<MessagesState>({ alerts: [], nextId: 1 });

// only exported for use in tests
export function resetAllMessages() {
  messages.value = { alerts: [], nextId: 1 };
}

export type AppendMessageFn = (text: string, level?: MessageLevel) => void;

const appendMessage: AppendMessageFn = (text: string, level: MessageLevel = "warning") => {
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

const removeAlert = (id: number) => {
  const alerts = messages.value.alerts.filter((a) => a.id !== id);
  messages.value = { ...messages.value, alerts };
};

export interface UseMessagesHook {
  alerts: Signal<MessageType[]>
  appendMessage: (level: MessageLevel, text: string, footer?: string) => void;
  removeAlert: (id: number) => void;
}

export function useMessages(): UseMessagesHook {
  const alerts = useComputed(() => {
    return messages.value.alerts;
  });

  return { alerts, appendMessage, removeAlert };
}
