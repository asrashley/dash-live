import { html } from "htm/preact";
import { routeMap } from '/libs/routemap.js';
import { Icon, Card } from '@dashlive/ui';

export function NoStreamsMessage() {
    return html`<${Card} header="Please add some media files">
    <p><${Icon} className="fs-2 me-2" name="camera-video-off" />There are no streams in the database. Please go
    to <a className="link" href="${routeMap.listStreams.url()}">the streams page</a> and
    add some streams.</p>
    </${Card}>`;
}