import { useEffect, useMemo } from 'preact/hooks'
import { html } from 'htm/preact';
import { Route, Switch } from "wouter-preact";

import { routeMap } from '/libs/routemap.js';

import { BreadCrumbs, MessagesPanel } from '@dashlive/ui';
import { ListStreamsPage } from './mps/components/ListStreamsPage.js';
import { AddStreamPage } from './mps/components/AddStreamPage.js';
import { EditStreamPage } from './mps/components/EditStreamPage.js';
import { HomePage } from './home/components/HomePage.js';

import { ApiRequests, EndpointContext } from './endpoints.js';
import { AppStateContext, createAppState } from './appState.js';

function NotFound(params) {
    return html`404, Sorry the page ${params["*"]} does not exist!`;
}

export function App({tokens, user}) {
  const apiRequests = useMemo(() => new ApiRequests(tokens), [tokens]);
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
