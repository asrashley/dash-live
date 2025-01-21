import { afterEach, describe, expect, test, vi } from "vitest";
import { act, renderHook } from "@testing-library/preact";

import { useWhoAmI } from "./useWhoAmI";
import { UserState } from "../types/UserState";
import { mediaUser } from "../test/MockServer";

describe('useWhoAmI hook', () => {
    const blankUser: Readonly<UserState> = {
        isAuthenticated: false,
        groups: [],
        permissions: {
            admin: false,
            media: false,
            user: false,
        },
    };
    const loggedInUser: Readonly<UserState> = {
        ...mediaUser,
        isAuthenticated: true,
        permissions: {
            admin: false,
            media: true,
            user: true,
        },
    }

    afterEach(() => {
        vi.clearAllMocks();
    });

    test('initial user state', () => {
        const { result } = renderHook(() => useWhoAmI());
        expect(result.current.user.value).toEqual(blankUser);
    });

    test('setState for a logged in user', () => {
        const { result } = renderHook(() => useWhoAmI());
        act(() => {
            result.current.setUser(mediaUser);
        });
        expect(result.current.user.value).toEqual(loggedInUser);
    });

    test('reset user', () => {
        const { result } = renderHook(() => useWhoAmI());
        act(() => {
            result.current.setUser(mediaUser);
        });
        act(() => {
            result.current.setUser(null);
        });
        expect(result.current.user.value).toEqual(blankUser);
    });
});