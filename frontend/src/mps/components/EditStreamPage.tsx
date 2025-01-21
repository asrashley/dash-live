import { useParams } from "wouter-preact";

import { EditStreamCard } from './EditStreamCard';
import { RouteParamsType } from "../../types/RouteParamsType";

import '../../styles/mps.less';

export default function EditStreamPage() {
  const {mps_name} = useParams<RouteParamsType>();
  return <EditStreamCard name={mps_name} />;
}
