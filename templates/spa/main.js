import { render } from 'preact';
import { html } from 'htm/preact';

import { App } from '{{ js_url("spa/app.js") }}';

const initialTokens = {{ initialTokens | toJson }};
const user = {{ user | toJson }};

render(html`<${App} tokens=${initialTokens} user=${user} />`, document.getElementById('app'));
