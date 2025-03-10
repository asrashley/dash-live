import { createContext } from 'preact';
import { signal, computed, type Signal, type ReadonlySignal } from "@preact/signals";
import { DialogState } from './types/DialogState';

export interface AppStateType {
  backdrop: ReadonlySignal<boolean>;
  cinemaMode: Signal<boolean>;
  dialog: Signal<DialogState | null>;
  closeDialog: () => void;
}

export const AppStateContext = createContext<AppStateType>(null);

export function createAppState(): AppStateType {
  const dialog = signal<DialogState | null>(null);
  const cinemaMode = signal<boolean>(false);

  const backdrop = computed(() => {
    return dialog.value?.backdrop === true;
  });

  const closeDialog = () => {
    dialog.value = null;
  };

  return { cinemaMode, dialog, backdrop, closeDialog };
}
