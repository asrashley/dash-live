import { type ComponentChildren } from "preact";
import { useContext } from "preact/hooks";

import { EndpointContext } from "./endpoints";
import { useWhoAmI, WhoAmIContext } from "./hooks/useWhoAmI";
import { LoadingSpinner } from "./components/LoadingSpinner";

export function WhoAmIProvider({ children }: { children: ComponentChildren}) {
  const apiRequests = useContext(EndpointContext);
  const whoAmI = useWhoAmI(apiRequests);

  if (!whoAmI.checked.value) {
    return <LoadingSpinner />;
  }
  return <WhoAmIContext.Provider value={whoAmI}>{ children }</WhoAmIContext.Provider>;
}
