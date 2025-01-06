import { useEffect, useMemo } from 'preact/hooks'
import { Route, Switch, useLocation } from "wouter-preact";
import lazy from 'preact-lazy';

import { routeMap } from '@dashlive/routemap';
import { BreadCrumbs } from './components/BreadCrumbs';
import { LoadingSpinner } from './components/LoadingSpinner';
import { MessagesPanel } from './components/MessagesPanel';

import { ApiRequests, ApiRequestsProps, EndpointContext } from './endpoints';
import { AppStateContext, createAppState } from './appState';
import { InitialUserState } from './types/UserState';

const AddStreamPage = lazy(() => import('./mps/components/AddStreamPage'), LoadingSpinner);
const EditStreamPage = lazy(() => import('./mps/components/EditStreamPage'), LoadingSpinner);
const HomePage = lazy(() => import('./home/components/HomePage'), LoadingSpinner);
const ListStreamsPage = lazy(() => import('./mps/components/ListStreamsPage'), LoadingSpinner);

function NotFound(params) {
    return <p>404, Sorry the page {params["*"]} does not exist!</p>;
}

export interface AppProps {
  tokens: ApiRequestsProps;
  user: InitialUserState;
}

export function App({tokens, user}: AppProps) {
  const setLocation = useLocation()[1];
  const apiRequests = useMemo(() => new ApiRequests({
    ...tokens,
    navigate: setLocation
  }), [setLocation, tokens]);
  const state = useMemo(() => createAppState(user), [user]);
  const { backdrop } = state;

  useEffect(() => {
    const elt = document.querySelector('.modal-backdrop');
    if (backdrop.value) {
      elt.classList.add('show');
      elt.classList.remove('hidden');
      document.body.classList.add('modal-open');
    } else {
      elt.classList.remove('show');
      elt.classList.add('hidden');
      document.body.classList.remove('modal-open');
    }
  }, [backdrop.value]);

  useEffect(() => {
    const spaNavigate = (ev: Event) => {
      ev.preventDefault();
      const href = (ev.target as HTMLAnchorElement).getAttribute('href');
      setLocation(href);
    };
    const links = document.querySelectorAll('.navbar .spa .nav-link');

    links.forEach((elt) => elt.addEventListener('click', spaNavigate));

    return () => {
      links.forEach((elt) => elt.removeEventListener('click', spaNavigate));
    };
  }, [setLocation]);

  return <AppStateContext.Provider value={state}>
  <BreadCrumbs />
  <EndpointContext.Provider value={apiRequests}>
    <MessagesPanel />
    <Switch>
      <Route component={ListStreamsPage} path={ routeMap.listMps.route } />
      <Route component={AddStreamPage} path={ routeMap.addMps.route } />
      <Route component={EditStreamPage} path={ routeMap.editMps.route } />
      <Route component={HomePage} path={ routeMap.home.route } />
      <Route path="*" component={NotFound} />
    </Switch>
  </EndpointContext.Provider>
</AppStateContext.Provider>;
}
