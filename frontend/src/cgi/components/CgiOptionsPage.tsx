import { useState } from "preact/hooks";

import { PingEventsTable } from "./PingEventsTable";
import { Scte35EventsTable } from "./Scte35EventsTable";
import { OptionsDetailTable } from "./OptionsDetailTable";
import { GenericParametersTable } from "./GenericParametersTable";

export default function CgiOptionsPage() {
  const [showDetails, setShowDetails] = useState<boolean>(false);
  const toggleDetails = () => {
    setShowDetails(!showDetails);
  };

  return (
    <div className="cgi-parameters">
      <span className="float-end">
        <a className="link" href="#" data-testid="toggle-details" onClick={toggleDetails}>
          details
        </a>
      </span>
      <p className="info">
        There are a number of CGI parameters that can be used to modify
        manifests, media segments and time sources.
      </p>
      {showDetails ? <OptionsDetailTable /> : ""}
      <GenericParametersTable />
      <PingEventsTable />
      <Scte35EventsTable />
    </div>
  );
}
