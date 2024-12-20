import { useCallback } from "preact/hooks";

import { Alert } from "./Alert";
import { useMessages } from "../hooks/useMessages";

export function MessagesPanel() {
  const { alerts, removeAlert } = useMessages();

  const onDismiss = useCallback(
    (id: number) => {
      removeAlert(id);
    },
    [removeAlert]
  );

  return (
    <div className="messages-panel">
      {alerts.value.map((item) => (
        <Alert key={item.id} onDismiss={onDismiss} {...item} />
      ))}
    </div>
  );
}
