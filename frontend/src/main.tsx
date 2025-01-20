import { render } from 'preact';
import { App } from './App'

import { navbar, initialTokens } from '@dashlive/init';

let root = document.getElementById('app');

if (root === null) {
    root = document.createElement('div');
    root.setAttribute('id', 'app');
    document.body.appendChild(root);
}

render(<App accessToken={initialTokens.accessToken} navbar={navbar} />, root);
