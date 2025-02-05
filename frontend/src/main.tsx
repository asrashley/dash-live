import { render } from 'preact';
import { App } from './App'

import './styles/main.less';

let root = document.getElementById('app');

if (root === null) {
    root = document.createElement('div');
    root.setAttribute('id', 'app');
    document.body.appendChild(root);
}

render(<App />, root);
