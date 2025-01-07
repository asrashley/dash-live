import { afterEach, describe, expect, test } from "vitest";
import { InitialApiTokens } from "./types/InitialApiTokens";
import { createAppState, getInitialState } from "./appState";
import { InitialUserState } from "./types/UserState";

describe('appState', () => {
    const blankApiTokens: InitialApiTokens = {
        csrfTokens: {
            files: null,
            kids: null,
            streams: null,
            upload: null
        },
        accessToken: null,
        refreshToken: null,
    };
    const loggedInApiTokens: InitialApiTokens = {
        csrfTokens: {
            files: "5n2yd7DjfxtYZevuV6YZUn1TvTSu15",
            kids: "deTPkXUgreT.1YPzOwC",
            streams: "$y$j9T$m0ti84j40b6TxDSshX13Q",
            upload: "$05Hwkbs27sKBPOSIrAKGOZD",
        },
        accessToken: {
            expires: new Date(Date.now() + 60_000).toISOString(),
            jti: "abc1234",
        },
        refreshToken: {
            expires: new Date(Date.now() + 3600_000).toISOString(),
            jti: "def3456",
        },
    };
    const loggedInUser: InitialUserState = {
        isAuthenticated: false,
        groups: ["MEDIA"],
    };

    function setupDOM(userInfo: InitialUserState, apiTokens: InitialApiTokens) {
        document.body.innerHTML = `<script type="application/json" id="initialTokens">${JSON.stringify(apiTokens)}</script>
        <script type="application/json" id="user">${JSON.stringify(userInfo)}</script>`;
    }

    afterEach(() => {
        document.body.innerHTML = '';
    });

    test('can get initial state from a DOM element', () => {
        const user: InitialUserState = {
            isAuthenticated: false,
            groups: [],
        };
        setupDOM(user, blankApiTokens);
        expect(getInitialState<InitialApiTokens>("initialTokens")).toEqual(blankApiTokens);
        expect(getInitialState<InitialUserState>("user")).toEqual(user);
    });

    test('can get initial state from a DOM element when logged in', () => {
        setupDOM(loggedInUser, loggedInApiTokens);
        expect(getInitialState<InitialApiTokens>("initialTokens")).toEqual(loggedInApiTokens);
        expect(getInitialState<InitialUserState>("user")).toEqual(loggedInUser);
    });

    test('throws error if unable to find DOM element', () => {
        expect(() => {
            getInitialState<InitialApiTokens>("initialTokens")
        }).toThrowError('Failed to find script element');
    });

    test('creates blank app state', () => {
        const appState = createAppState();
        expect(appState.user.value).toEqual({
            isAuthenticated: false,
            groups: [],
            permissions: {
                admin: false,
                media: false,
                user: false,
              },
        });
        expect(appState.backdrop.value).toEqual(false);
        appState.dialog.value = {
            backdrop: true,
        };
        expect(appState.backdrop.value).toEqual(true);
    });

    test('creates app state for logged in user', () => {
        const appState = createAppState(loggedInUser);
        expect(appState.user.value).toEqual({
            ...loggedInUser,
            permissions: {
                admin: false,
                media: true,
                user: false,
              },
        });
    });
});