import { useContext } from "preact/hooks";
import { useComputed } from "@preact/signals";
import { Link } from "wouter-preact";

import { uiRouteMap } from "@dashlive/routemap";
import { WhoAmIContext } from "../../hooks/useWhoAmI";

export interface ButtonToolbarProps {
  errors,
  onSaveChanges,
  deleteStream,
  model,
  newStream: boolean;
}

export function ButtonToolbar({errors, onSaveChanges, deleteStream, model, newStream}: ButtonToolbarProps) {
  const { user } = useContext(WhoAmIContext);
  const cancelUrl = uiRouteMap.listMps.url();
  const disableSave = useComputed(() => {
    if (Object.keys(errors.value).length > 0) {
      return true;
    }
    return model.value.modified !== true;
  });

  if (!user.value.permissions.media) {
    return <div className="btn-toolbar">
      <Link className="btn btn-primary m-2" to={cancelUrl}>Back</Link></div>;
  }

  if (newStream) {
    return <div className="btn-toolbar">
    <button className="btn btn-success m-2" disabled={disableSave.value}
      onClick={onSaveChanges} >Save new stream</button>
    <Link class="btn btn-danger m-2" to={cancelUrl}>Cancel</Link>
  </div>;
  }

  const linkClass = `btn m-2 ${model.value.modified ? 'btn-warning': 'btn-primary'}`;

  return <div className="btn-toolbar">
    <button className="btn btn-success m-2" disabled={disableSave.value}
      onClick={onSaveChanges} >Save Changes</button>
    <button className="btn btn-danger m-2" onClick={deleteStream}>Delete Stream</button>
  <Link className={linkClass} to={cancelUrl}>
      {model.value.modified ? "Discard Changes" : "Back"}
    </Link>
  </div>;
}

