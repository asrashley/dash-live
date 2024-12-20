import { useContext } from 'preact/hooks'

import { Icon } from "../../components/Icon";
import { AllMultiPeriodStreamsContext } from '../../hooks/useAllMultiPeriodStreams';

export interface SortIconProps {
  name: string;
}

export function SortIcon({name}: SortIconProps) {
  const { sortField, sortAscending } = useContext(AllMultiPeriodStreamsContext);
  const opacity = sortField === name ? 100 : 50;
  const iconName = (sortField === name && !sortAscending) ? "sort-alpha-up" : "sort-alpha-down";

  return <Icon name={iconName} className={`opacity-${opacity}`} />;
}
