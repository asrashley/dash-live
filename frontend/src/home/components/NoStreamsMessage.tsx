import { routeMap } from "@dashlive/routemap";
import { Card } from "../../components/Card";
import { Icon } from "../../components/Icon";

export function NoStreamsMessage() {
  return (
    <Card id="no-streams-msg" header="Please add some media files">
      <p>
        <Icon className="fs-2 me-2" name="camera-video-off" />
        There are no streams in the database. Please go to{" "}
        <a className="link" href={routeMap.listStreams.url()}>
          the streams page
        </a>{" "}
        and add some streams.
      </p>
    </Card>
  );
}
