import { useContext } from 'preact/hooks';
import { AppStateContext } from '../appState';
import { useComputed } from '@preact/signals';


export function ModalBackdrop() {
  const { backdrop } = useContext(AppStateContext);
  const className = useComputed<string>(() => `modal-backdrop ${backdrop.value ? "show" : "d-none"}`);
  return <div data-testid="modal-backdrop" className={className} />;
}
