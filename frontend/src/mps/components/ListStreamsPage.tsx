import { type ComponentChildren } from 'preact';
import { Link } from 'wouter-preact';
import { useCallback, useContext } from 'preact/hooks'

import { useAllMultiPeriodStreams, AllMultiPeriodStreamsContext } from '../../hooks/useAllMultiPeriodStreams';
import { uiRouteMap } from '@dashlive/routemap';
import { SortIcon } from './SortIcon';
import { WhoAmIContext } from '../../user/hooks/useWhoAmI';

interface TableRowProps {
  name: string;
  title: string;
  periods: number[],
  duration: string;
}
function TableRow({name, title, periods, duration}: TableRowProps) {
  const url = uiRouteMap.editMps.url({mps_name: name});
  return <tr>
      <td className="name text-center">
        <Link to={ url }>{ name }</Link>
      </td>
      <td className="title text-center">
        <Link to={ url }>{ title }</Link>
      </td>
      <td className="num-periods text-end">
        { periods.length }
      </td>
      <td className="duration text-end">
        { duration }
      </td>
    </tr>;
}

interface SortableHeadingProps {
  name: string;
  children: ComponentChildren;
  className?: string;
}

function SortableHeading({name, children, className=""}: SortableHeadingProps) {
  const { sort, sortField, sortAscending } = useContext(AllMultiPeriodStreamsContext);
  const bold = name === sortField ? 'fw-bolder': '';
  const setSort = useCallback((ev: Event) => {
    ev.preventDefault();
    const ascending = name === sortField ? !sortAscending : true;
    sort(name, ascending);
  }, [name, sort, sortAscending, sortField]);

  return <th className={`${name} ${className}`}>
  <a onClick={setSort} className={`link-light ${bold}`}><SortIcon name={name} />{children}</a>
  </th>;
}

export default function ListStreamsPage() {
  const { user } = useContext(WhoAmIContext);
  const allMpsContext = useAllMultiPeriodStreams();
  const canModify = user.value.permissions.media === true;

  return <AllMultiPeriodStreamsContext.Provider value={allMpsContext}>
  <h1>Available Multi-period DASH streams</h1>
  <table className="table table-striped" id="mp-streams">
    <caption>Multi-Period Streams</caption>
    <thead>
      <tr>
        <SortableHeading name="name">Name</SortableHeading>
        <SortableHeading name="title">Title</SortableHeading>
        <th className="num-periods text-end">Periods</th>
        <th className="duration text-end">Duration</th>
      </tr>
    </thead>
    <tbody>
      { allMpsContext.streams.value.map(item => <TableRow key={item.name} {...item} />)}
    </tbody>
  </table>
  <div class="btn-toolbar">
    {canModify && <Link className="btn btn-primary btn-sm m-2"
      href={uiRouteMap.addMps.url()} >Add a Stream</Link> }
  </div>
</AllMultiPeriodStreamsContext.Provider>;
}
