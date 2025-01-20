import { renderHook } from "@testing-library/preact";
import { afterAll, afterEach, describe, expect, test, vi } from "vitest";
import { LocalStorageKeys, useLocalStorage } from "./useLocalStorage";
import { defaultCgiOptions } from "@dashlive/options";

describe('useLocalStorage hook', () => {
    const defaultDashOptions = {
        ...defaultCgiOptions,
        manifest: "hand_made.mpd",
        mode: "vod",
        stream: undefined,
    };
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    afterEach(() => {
        localStorage.clear();
        vi.clearAllMocks();
    });

    afterAll(() => {
        vi.restoreAllMocks();
    })

    test('empty local storage', () => {
        const { result } = renderHook(() => useLocalStorage());
        const { dashOptions, refreshToken } = result.current;
        expect(refreshToken.value).toBeNull();
        expect(dashOptions.value).toEqual(defaultDashOptions);
        expect(warnSpy).not.toHaveBeenCalled();
    });

    test('loads DASH options', () => {
        localStorage.setItem(LocalStorageKeys.DASH_OPTIONS, JSON.stringify({
            mode: 'live',
            stream: 'demo',
        }));
        const { result } = renderHook(() => useLocalStorage());
        const { dashOptions } = result.current;
        expect(dashOptions.value).toEqual({
            ...defaultDashOptions,
            mode: 'live',
            stream: 'demo',
        });
        expect(warnSpy).not.toHaveBeenCalled();
    });

    test('can set a DASH option', () => {
        const { result } = renderHook(() => useLocalStorage());
        const { dashOptions, setDashOption } = result.current;
        setDashOption('mode', 'live');
        setDashOption('abr', false);
        expect(dashOptions.value).toEqual({
            ...defaultDashOptions,
            mode: 'live',
            abr: '0',
        });
        setDashOption('abr', true);
        expect(dashOptions.value).toEqual({
            ...defaultDashOptions,
            mode: 'live',
            abr: '1',
        });
        expect(warnSpy).not.toHaveBeenCalled();
    });

    test('invalid JSON in DASH option key', () => {
        localStorage.setItem(LocalStorageKeys.DASH_OPTIONS, "not valid JSON");
        const { result } = renderHook(() => useLocalStorage());
        const { dashOptions, refreshToken } = result.current;
        expect(refreshToken.value).toBeNull();
        expect(dashOptions.value).toEqual(defaultDashOptions);
        expect(warnSpy).toHaveBeenCalled();
    });

    test('loads refresh token', () => {
        localStorage.setItem(LocalStorageKeys.REFRESH_TOKEN, JSON.stringify({
            expires: 'expires',
            jwt: 'jwt',
        }));
        const { result } = renderHook(() => useLocalStorage());
        const { refreshToken } = result.current;
        expect(refreshToken.value).toEqual({
            expires: 'expires',
            jwt: 'jwt',
        });
        expect(warnSpy).not.toHaveBeenCalled();
    });

    test('can set refresh token', () => {
        const { result } = renderHook(() => useLocalStorage());
        const { setRefreshToken } = result.current;
        setRefreshToken({ expires: 'expires', jwt: 'jwt' });
        expect(JSON.parse(localStorage.getItem(LocalStorageKeys.REFRESH_TOKEN))).toEqual({
            expires: 'expires',
            jwt: 'jwt',
        });
    });

    test('clears refresh token', () => {
        localStorage.setItem(LocalStorageKeys.REFRESH_TOKEN, JSON.stringify({
            expires: 'expires',
            jwt: 'jwt',
        }));
        const { result } = renderHook(() => useLocalStorage());
        const { setRefreshToken } = result.current;
        setRefreshToken(null);
        expect(localStorage.getItem(LocalStorageKeys.REFRESH_TOKEN)).toBeNull();
        expect(warnSpy).not.toHaveBeenCalled();
    });

    test('invalid JSON in refresh token option key', () => {
        localStorage.setItem(LocalStorageKeys.REFRESH_TOKEN, "not valid JSON");
        const { result } = renderHook(() => useLocalStorage());
        const { refreshToken } = result.current;
        expect(refreshToken.value).toBeNull();
        expect(warnSpy).toHaveBeenCalled();
    });

});