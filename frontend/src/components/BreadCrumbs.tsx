import { useCallback } from "preact/hooks";
import { useBreadcrumbs, type BreadCrumbItem } from "../hooks/useBreadcrumbs";

interface CrumbItemProps extends BreadCrumbItem {
  setLocation: (url: string) => void;
}

function CrumbItem({ title, href, active, id, setLocation }: CrumbItemProps) {
  const followInternalLink = useCallback(
    (ev: Event) => {
      const elt = ev.target as HTMLAnchorElement;
      const href = elt.getAttribute("href");
      ev.preventDefault();
      setLocation(href);
      return false;
    },
    [setLocation]
  );

  const body = active ? (
    <span>{title}</span>
  ) : (
    <a href={href} title={title} onClick={followInternalLink}>
      {title}
    </a>
  );
  const className = `breadcrumb-item ${active ? "active" : ""}`;
  return (
    <li id={id} className={className}>
      {body}
    </li>
  );
}

export function BreadCrumbs() {
  const { breadcrumbs, location, setLocation } = useBreadcrumbs();

  return (
    <nav
      className="breadcrumbs"
      aria-label="breadcrumb"
      data-location={location}
    >
      <ol className="breadcrumb">
        {breadcrumbs.map((crumb) => (
          <CrumbItem key={crumb.id} setLocation={setLocation} {...crumb} />
        ))}
      </ol>
    </nav>
  );
}
