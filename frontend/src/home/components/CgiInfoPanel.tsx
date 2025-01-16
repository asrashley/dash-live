import { uiRouteMap } from '@dashlive/routemap';

export function CgiInfoPanel() {
    return <p className="info">
      The MPD files for live streams are dynamically generated so that they
      appear to be live sources, using static media files. Requests for
      manifests and for media fragments can be modified using various CGI
      parameters, which are documented on the <a href={uiRouteMap.cgiOptions.url()}
      className="link">CGI options</a> page.
    </p>;
}
