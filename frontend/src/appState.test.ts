import { describe, expect, test } from "vitest";
import { createAppState } from "./appState";
import { act } from "preact/test-utils";

describe('appState', () => {
    test('creates blank app state', () => {
        const appState = createAppState();
        expect(appState.backdrop.value).toEqual(false);
        act(() => {
            appState.dialog.value = {
                backdrop: true,
            };
        });
        expect(appState.backdrop.value).toEqual(true);
    });

});