import { uiRouteMap } from '@dashlive/routemap';
import { Link } from 'wouter-preact';

export function CgiInfoPanel() {
    return <p className="info">
      The MPD files for live streams are dynamically generated so that they
      appear to be live sources, using static media files. Requests for
      manifests and for media fragments can be modified using various CGI
      parameters, which are documented on the <Link href={uiRouteMap.cgiOptions.url()}
      className="link">CGI options</Link> page.
    </p>;
}
