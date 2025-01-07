import type { ComponentChildren } from "preact";
import { useCallback, useState } from "preact/hooks";
import { MenuItemType } from "../types/MenuItemType";

export interface DropDownItemProps extends Omit<MenuItemType, "title"> {
  index: number;
  children: ComponentChildren;
  setExpanded: (value: boolean) => void;
}

function DropDownItem({
  href = "#",
  index,
  onClick,
  setExpanded,
  children,
}: DropDownItemProps) {
  const click = useCallback(
    (ev) => {
      ev.preventDefault();
      setExpanded(false);
      onClick(ev);
    },
    [onClick, setExpanded]
  );
  return (
    <li data-testid={`ddi_${index}`}>
      <a className="dropdown-item" href={href} onClick={click}>
        {children}
      </a>
    </li>
  );
}

export interface DropDownMenuProps {
  children?: ComponentChildren;
  linkClass?: string;
  menu: MenuItemType[];
}
export function DropDownMenu({
  children,
  menu,
  linkClass = "btn btn-secondary",
}: DropDownMenuProps) {
  const [expanded, setExpanded] = useState(false);

  const toggleMenu = (ev) => {
    ev.preventDefault();
    setExpanded(!expanded);
  };

  const show = expanded ? " show" : "";

  return (
    <div className="dropdown">
      <a
        class={`${linkClass} dropdown-toggle${show}`}
        href="#"
        onClick={toggleMenu}
        role="button"
        aria-expanded={expanded}
      >
        {children}
      </a>
      <ul className={`dropdown-menu ${show}`}>
        {menu.map((item, index) => (
          <DropDownItem
            key={item.title}
            index={index}
            onClick={item.onClick}
            setExpanded={setExpanded}
            href={item.href}
          >
            {item.title}
          </DropDownItem>
        ))}
      </ul>
    </div>
  );
}
