import { createContext } from 'preact';
import { signal, computed, type Signal, type ReadonlySignal } from "@preact/signals";
import { DialogState } from './types/DialogState';

export interface AppStateType {
  backdrop: ReadonlySignal<boolean>;
  dialog: Signal<DialogState>;
}

export const AppStateContext = createContext<AppStateType>(null);

export function createAppState(): AppStateType {
  const dialog = signal(null);

  const backdrop = computed(() => {
    return dialog.value?.backdrop === true;
  });

  return { dialog, backdrop };
}
