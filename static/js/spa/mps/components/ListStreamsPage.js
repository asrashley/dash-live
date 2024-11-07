import { html } from 'htm/preact';
import { Link } from 'wouter-preact';
import { useCallback, useContext } from 'preact/hooks'

import { Icon} from '@dashlive/ui';
import { useAllMultiPeriodStreams, AllMultiPeriodStreamsContext } from '@dashlive/hooks';
import { AppStateContext } from '../../appState.js';
import { routeMap } from '/libs/routemap.js';

function TableRow({name, title, periods, duration}) {
  const url = routeMap.editMps.url({mps_name: name});
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

function SortIcon({name}) {
  const { sortField, sortAscending } = useContext(AllMultiPeriodStreamsContext);
  const opacity = sortField === name ? 100 : 50;
  const iconName = (sortField === name && !sortAscending) ? "sort-alpha-up" : "sort-alpha-down";

  return html`<${Icon} name="${iconName}" className="opacity-${opacity}"/>`;
}

function SortableHeading({name, children, className=""}) {
  const { sort, sortField, sortAscending } = useContext(AllMultiPeriodStreamsContext);
  const bold = name === sortField ? 'fw-bolder': '';
  const setSort = useCallback((ev) => {
    ev.preventDefault();
    const ascending = name === sortField ? !sortAscending : true;
    sort(name, ascending);
  }, [name, sort, sortAscending, sortField]);

  return html`<th class="${name} ${className}">
  <a onClick=${setSort} class="link-light ${bold}"><${SortIcon} name=${name}/>
  ${children}</a>
  </th>`;
}

export function ListStreamsPage() {
  const { user } = useContext(AppStateContext);
  const allMpsContext = useAllMultiPeriodStreams();
  const canModify = user.value.permissions.media === true;

  return html`
<${AllMultiPeriodStreamsContext.Provider} value=${allMpsContext}>
  <h1>Available Multi-period DASH streams</h1>
  <table class="table table-striped" id="mp-streams">
    <caption>Multi-Period Streams</caption>
    <thead>
      <tr>
        <${SortableHeading} name="name">Name<//>
        <${SortableHeading} name="title">Title<//>
        <th className="num-periods text-end">Periods</th>
        <th className="duration text-end">Duration</th>
      </tr>
    </thead>
    <tbody>
      ${ allMpsContext.streams.value.map(item => html`<${TableRow} ...${item} />`)}
    </tbody>
  </table>
  <div class="btn-toolbar">
    ${canModify && html`<${Link} class="btn btn-primary btn-sm m-2"
      href=${routeMap.addMps.url()} >Add a Stream</${Link}>` }
  </div>
</${AllMultiPeriodStreamsContext.Provider}>`;
}
