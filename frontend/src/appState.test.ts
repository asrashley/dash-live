import { afterEach, describe, expect, test } from "vitest";
import { createAppState } from "./appState";
import { InitialUserState } from "./types/UserState";

describe('appState', () => {
    const loggedInUser: InitialUserState = {
        isAuthenticated: false,
        groups: ["MEDIA"],
    };

    afterEach(() => {
        document.body.innerHTML = '';
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