import { type JSX } from "preact";

export interface MenuItemType {
    onClick: (ev: JSX.TargetedEvent<HTMLAnchorElement>) => void;
    href?: string;
    title: string;
}
