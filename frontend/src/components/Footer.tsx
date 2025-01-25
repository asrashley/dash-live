import { useRef } from "preact/hooks";

declare const _GIT_HASH_: string;

export function Footer() {
    const year = useRef<number>(new Date().getFullYear());
    return <footer className="bg-body-tertiary footer row border-top border-secondary-subtle">
    <div className="col-3 github-link">
      <div><a href="https://github.com/asrashley/dash-live">github.com/asrashley/dash-live</a></div>
      <div>{_GIT_HASH_}</div>
    </div>
    <div className="col-6 text-center service-name">Simulated MPEG DASH service</div>
    <div className="col-3 text-end copyright">&copy;{year.current} Alexis Ashley</div>
  </footer>;

}