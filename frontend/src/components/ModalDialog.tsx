import { type ComponentChildren } from "preact";

export interface ModalDialogProps {
  children?: ComponentChildren;
  footer?: ComponentChildren;
  id?: string;
  size?: "sm" | "lg" | "xl";
  title: string;
  onClose: () => void;
}

export function ModalDialog({
  id = "dialog-box",
  title,
  children,
  footer,
  size,
  onClose,
}: ModalDialogProps) {
  const classNames: string[] = ["modal-dialog"];
  if (size !== undefined) {
    classNames.push(`modal-${size}`);
  }
  if (footer === undefined) {
    footer = (
      <button
        type="button"
        className="btn btn-secondary btn-secondary"
        onClick={onClose}
      >
        Close
      </button>
    );
  }

  return (
    <div
      className="modal fade show"
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      id={id}
      style="display: block"
    >
      <div className={classNames.join(" ")} role="document">
        <div className="modal-content">
          <div className="modal-header">
            <h5 className="modal-title">{title}</h5>
            <button
              type="button"
              className="close btn-close"
              aria-label="Close"
              onClick={onClose}
             />
          </div>
          <div className="modal-body m-2">{children}</div>
          <div className="modal-footer">{footer}</div>
        </div>
      </div>
    </div>
  );
}
