import { Fragment } from "preact";
import { useContext } from "preact/hooks";

import { routeMap, uiRouteMap } from "@dashlive/routemap";

import { Card } from "../../components/Card";
import { Icon } from "../../components/Icon";
import { WhoAmIContext } from "../../user/hooks/useWhoAmI";

function PleaseLogin() {
  const { user } = useContext(WhoAmIContext);

  if (user.value.isAuthenticated) {
    return null;
  }
  return <Fragment><a className="link" data-testid="needs-login" href={uiRouteMap.login.url()}>login</a> and then </Fragment>;
}

export function NoStreamsMessage() {
  return (
    <Card id="no-streams-msg" header="Please add some media files">
      <p>
        <Icon className="fs-2 me-2" name="camera-video-off" />
        There are no streams in the database.
        Please <PleaseLogin />go to <a className="link" href={routeMap.listStreams.url()}>
          the streams page
        </a>{" "}to add some media files.
      </p>
    </Card>
  );
}
