import { type JSX } from "preact";

import { MenuItemType } from "../../types/MenuItemType";
import { DropDownMenu } from "../../components/DropDownMenu";
import { Icon } from '../../components/Icon';

export interface PeriodOrderProps {
  addPeriod: (ev: JSX.TargetedEvent<HTMLAnchorElement>) => void;
  deletePeriod: (ev: JSX.TargetedEvent<HTMLAnchorElement>) => void;
}

export function PeriodOrder({ addPeriod, deletePeriod }: PeriodOrderProps) {
  const menu: MenuItemType[] = [
    {
      title: "Add another Period",
      onClick: addPeriod,
    },
    {
      title: "Delete Period",
      onClick: deletePeriod,
    },
  ];

  return <DropDownMenu linkClass="" menu={menu}>
    <Icon name="three-dots" />
  </DropDownMenu>;
}
