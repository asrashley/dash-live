import { useLocation, useRouter } from 'wouter-preact';

export const useBreadcrumbs = () => {
    const [location, setLocation] = useLocation();
    const { base } = useRouter();

    const baseParts = base === "" ? [""] : base.split('/');
    const parts = location === "/" ? [""] : location.split('/').slice(baseParts.length - 1);

    const breadcrumbs = parts.map((title, idx) => {
      const href = idx === 0 ? `${base}/` : `${base}${parts.slice(0, idx + 1).join('/')}`;
      const active = idx == (parts.length - 1);
      const id = `crumb_${idx}`;
      if (title === '') {
        title = 'Home';
      }
      return {title, active, href, id};
    });

    return {breadcrumbs, location, setLocation};
  };

