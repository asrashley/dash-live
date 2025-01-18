import { afterEach, describe, expect, test, vi } from "vitest";
import { act, renderHook } from "@testing-library/preact";
import { mock } from "vitest-mock-extended";

import { useWhoAmI, UseWhoAmIHook } from "./useWhoAmI";
import { ApiRequests } from "../endpoints";
import { UserState } from "../types/UserState";
import { LoginResponse } from "../types/LoginResponse";
import { mediaUser } from "../test/MockServer";

describe('useWhoAmI hook', () => {
    const apiRequests = mock<ApiRequests>();
    const blankUser: Readonly<UserState> = {
        isAuthenticated: false,
        groups: [],
        permissions: {
            admin: false,
            media: false,
            user: false,
        },
    }

    afterEach(() => {
        vi.clearAllMocks();
    });

    test('initial user state, no refresh token', async () => {
        apiRequests.getUserInfo.mockResolvedValue(new Response(null, {status: 401}));
        const { result } = renderHook<UseWhoAmIHook, [ApiRequests]>(() => useWhoAmI(apiRequests));
        await Promise.resolve();
        expect(result.current.checked.value).toEqual(true);
        expect(apiRequests.getUserInfo).toHaveBeenCalled();
    });

    test('initial user state, expired refresh token', async () => {
        const stopper = Promise.withResolvers<void>();
        const prom = new Promise<void>(resolve => {
            apiRequests.getUserInfo.mockImplementation(async () => {
                await stopper;
                resolve();
                return new Response(null, { status: 401 });
            });
        });
        const { result } = renderHook(() => useWhoAmI(apiRequests));
        expect(result.current.checked.value).toEqual(false);
        expect(result.current.user.value).toEqual(blankUser);
        await act(async () => {
            stopper.resolve();
            await expect(prom).resolves.toBeUndefined();
        });
        expect(result.current.checked.value).toEqual(true);
        expect(result.current.user.value).toEqual(blankUser);
    });

    test('user signal for a logged in user', async () => {
        const prom = new Promise<void>(resolve => {
            apiRequests.getUserInfo.mockImplementation(async () => {
                const response: LoginResponse = {
                    success: true,
                    mustChange: false,
                    csrf_token: 'abnc',
                    user: {
                        ...mediaUser,
                        isAuthenticated: true,
                    }
                };
                resolve();
                return response;
            });
        });
        const { result } = renderHook(() => useWhoAmI(apiRequests));
        await expect(prom).resolves.toBeUndefined();
        expect(result.current.user.value).toEqual({
            ...mediaUser,
            isAuthenticated: true,
            permissions: {
                admin: false,
                media: true,
                user: true,
            },
        });
    });

});