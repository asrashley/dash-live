import { type ComponentChildren } from 'preact';
import { useEffect, useMemo } from 'preact/hooks'
import { Route, Switch, useLocation } from "wouter-preact";
import lazy from 'preact-lazy';

import { uiRouteMap } from '@dashlive/routemap';
import { navbar } from '@dashlive/init';
import { LoadingSpinner } from './components/LoadingSpinner';
import { MessagesPanel } from './components/MessagesPanel';
import { ModalBackdrop } from './components/ModalBackdrop';
import { NavHeader } from './components/NavHeader';

import { ApiRequests, EndpointContext } from './endpoints';
import { AppStateContext, AppStateType, createAppState } from './appState';
import { InitialUserState } from './types/UserState';
import { InitialApiTokens } from './types/InitialApiTokens';
import { PageNotFound } from './components/PageNotFound';

const AddStreamPage = lazy(() => import('./mps/components/AddStreamPage'), LoadingSpinner);
const EditStreamPage = lazy(() => import('./mps/components/EditStreamPage'), LoadingSpinner);
const HomePage = lazy(() => import('./home/components/HomePage'), LoadingSpinner);
const ListStreamsPage = lazy(() => import('./mps/components/ListStreamsPage'), LoadingSpinner);

export interface AppProps {
  tokens: InitialApiTokens;
  user: InitialUserState;
  children?: ComponentChildren;
}

export function App({children, tokens, user}: AppProps) {
  const setLocation = useLocation()[1];
  const apiRequests = useMemo(() => new ApiRequests({
    ...tokens,
    navigate: setLocation
  }), [setLocation, tokens]);
  const state: AppStateType = useMemo(() => createAppState(user), [user]);
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

  return <AppStateContext.Provider value={state}>
  <EndpointContext.Provider value={apiRequests}>
    <NavHeader navbar={navbar} />
    <MessagesPanel />
    <div className="content container-fluid">
      <Switch>
        <Route component={ListStreamsPage} path={ uiRouteMap.listMps.route } />
        <Route component={AddStreamPage} path={ uiRouteMap.addMps.route } />
        <Route component={EditStreamPage} path={ uiRouteMap.editMps.route } />
        <Route component={HomePage} path={ uiRouteMap.home.route } />
        <Route path="*" component={PageNotFound} />
      </Switch>
      { children }
    </div>
    <ModalBackdrop />
  </EndpointContext.Provider>
</AppStateContext.Provider>;
}
