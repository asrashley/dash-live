import { render } from 'preact';
import { App } from './App'
import { getInitialState } from './appState';
import { InitialUserState } from './types/UserState';
import { InitialApiTokens } from './types/InitialApiTokens';

const initialTokens = getInitialState<InitialApiTokens>("initialTokens");
const user = getInitialState<InitialUserState>("user");

let root = document.getElementById('app');

if (root === null) {
    root = document.createElement('div');
    root.setAttribute('id', 'app');
    document.body.appendChild(root);
}

render(<App tokens={initialTokens} user={user} />, root);
