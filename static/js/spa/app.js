import { useEffect, useMemo } from 'preact/hooks'
import { html } from 'htm/preact';
import { Route, Switch, useLocation } from "wouter-preact";
import lazy from 'preact-lazy';

import { routeMap } from '/libs/routemap.js';

import { BreadCrumbs, LoadingSpinner, MessagesPanel } from '@dashlive/ui';

import { ApiRequests, EndpointContext } from './endpoints.js';
import { AppStateContext, createAppState } from './appState.js';

const AddStreamPage = lazy(() => import('./mps/components/AddStreamPage.js'), LoadingSpinner);
const EditStreamPage = lazy(() => import('./mps/components/EditStreamPage.js'), LoadingSpinner);
const HomePage = lazy(() => import('./home/components/HomePage.js'), LoadingSpinner);
const ListStreamsPage = lazy(() => import('./mps/components/ListStreamsPage.js'), LoadingSpinner);

function NotFound(params) {
    return html`404, Sorry the page ${params["*"]} does not exist!`;
}

export function App({tokens, user}) {
  const apiRequests = useMemo(() => new ApiRequests(tokens), [tokens]);
  const state = useMemo(() => createAppState(user), [user]);
  const setLocation = useLocation()[1];
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
    const spaNavigate = (ev) => {
      ev.preventDefault();
      const href = ev.target.getAttribute('href');
      setLocation(href);
    };
    const links = document.querySelectorAll('.navbar .spa .nav-link');

    links.forEach((elt) => elt.addEventListener('click', spaNavigate));

    return () => {
      links.forEach((elt) => elt.removeEventListenerEventListener('click', spaNavigate));
    };
  }, [setLocation]);

  return html`
<${AppStateContext.Provider} value=${state}>
  <${BreadCrumbs} />
  <${EndpointContext.Provider} value=${apiRequests}>
    <${MessagesPanel} />
    <${Switch}>
      <${Route} component=${ListStreamsPage} path="${ routeMap.listMps.route }"/>
      <${Route} component=${AddStreamPage} path="${ routeMap.addMps.route }"/>
      <${Route} component=${EditStreamPage} path="${ routeMap.editMps.route }"/>
      <${Route} component=${HomePage} path="${ routeMap.home.route }"/>
      <${Route} path="*" component=${NotFound} />
    </${Switch}>
  </${EndpointContext.Provider}>
</${AppStateContext.Provider}>
`;
}
