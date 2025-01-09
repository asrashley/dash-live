import { useContext } from 'preact/hooks';
import { AppStateContext } from '../appState';


export function ModalBackdrop() {
  const { backdrop } = useContext(AppStateContext);
  const className = `modal-backdrop ${backdrop.value ? "show" : "hidden"}`;
  return <div className={className} />;
}
