import { useMemo } from 'preact/hooks';
import { useLocation } from 'wouter-preact';

export const useBreadcrumbs = () => {
    const [location, setLocation] = useLocation();

    const breadcrumbs = useMemo(() => {
      const parts = location === "/" ? [""] : location.split('/');

      return parts.map((title, idx) => {
        const href = idx === 0 ? '/' : parts.slice(0, idx + 1).join('/');
        const active = idx === (parts.length - 1);
        const id = `crumb_${idx}`;
        if (title === '') {
         title = 'Home';
        }
        return {title, active, href, id};
      });
    }, [location]);

    return {breadcrumbs, location, setLocation};
  };

