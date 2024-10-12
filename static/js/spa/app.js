import { useEffect, useMemo } from 'preact/hooks'
import { html } from 'htm/preact';
import { Route, Switch } from "wouter-preact";

import { routeMap } from '/libs/routemap.js';

import { BreadCrumbs } from './components/BreadCrumbs.js';
import { MessagesPanel } from './components/MessagesPanel.js';
import { ListStreamsPage } from './mps/components/ListStreamsPage.js';
import { AddStreamPage } from './mps/components/AddStreamPage.js';
import { EditStreamPage } from './mps/components/EditStreamPage.js';
import { ApiRequests, EndpointContext } from './endpoints.js';
import { AppStateContext, createAppState } from './appState.js';

function NotFound(params) {
    return html`404, Sorry the page ${params["*"]} does not exist!`;
}

function translateUrlTemplate(urlTemplate) {
  const re = /{([a-z_]+)}/g;
  return urlTemplate.replaceAll(re, ':$1')
}

const paths = Object.fromEntries(
  Object.entries(routeMap).map(
    ([name, {template}]) => [name, translateUrlTemplate(template)]));

export function App({tokens}) {
  const apiRequests = useMemo(() => new ApiRequests(tokens), [tokens]);
  const state = useMemo(createAppState, []);
  const { backdrop, messages } = state;

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
    <${MessagesPanel} messages=${messages} />
    <${Switch}>
      <${Route} component=${ListStreamsPage} path="${ paths.listMps }"/>
      <${Route} component=${AddStreamPage} path="${ paths.addMps }"/>
      <${Route} component=${EditStreamPage} path="${ paths.editMps }"/>
      <${Route} path="*" component=${NotFound} />
    </${Switch}>
  </${EndpointContext.Provider}>
</${AppStateContext.Provider}>
`;
}
