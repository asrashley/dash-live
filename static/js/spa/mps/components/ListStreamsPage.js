import { html } from 'htm/preact';
import { Link } from 'wouter-preact';
import { useEffect, useState, useContext } from 'preact/hooks'

import { EndpointContext, urlFor } from '../../endpoints.js';

function TableRow({name, title, periods, duration}) {
  const url = urlFor.editMps({name});
  return html`
    <tr>
      <td class="name text-center">
        <${Link} to="${ url }">${ name }</${Link}>
      </td>
      <td class="title text-center">
        <${Link} to="${ url }">${ title }</${Link}>
      </td>
      <td class="num-periods text-end">
        ${ periods.length }
      </td>
      <td class="duration text-end">
        ${ duration }
      </td>
    </tr>
`;
}

export function ListStreamsPage() {
  const [streams, setStreams] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const apiRequests = useContext(EndpointContext);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchStreamsIfRequired = async () => {
      if (!loaded) {
        const data = await apiRequests.getAllMultiPeriodStreams({signal});
        setLoaded(true);
        setStreams(data.streams);
      }
    };

    fetchStreamsIfRequired();

    return () => {
      controller.abort();
    };
  }, [apiRequests, loaded]);

  return html`
<div>
  <h1>Available Multi-period DASH streams</h1>
  <table class="table table-striped" id="mp-streams">
    <caption>Multi-Period Streams</caption>
    <thead>
      <tr>
        <th class="name">Name</th>
        <th class="title">Title</th>
        <th class="num-periods text-end">Periods</th>
        <th class="duration text-end">Duration</th>
      </tr>
    </thead>
    <tbody>
      ${ streams.map(item => html`<${TableRow} ...${item} />`)}
    </tbody>
  </table>
  <div class="btn-toolbar">
    <${Link} class="btn btn-primary btn-sm m-2"
      href=${urlFor.addMps()} >Add a Stream</${Link}>
  </div>
</div>
`;
}
