import { render } from 'preact';
import { App } from './App'

import { user, initialTokens } from '@dashlive/init';

let root = document.getElementById('app');

if (root === null) {
    root = document.createElement('div');
    root.setAttribute('id', 'app');
    document.body.appendChild(root);
}

render(<App tokens={initialTokens} user={user} />, root);
