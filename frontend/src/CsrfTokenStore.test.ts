import { beforeEach, describe, test, vi } from 'vitest';
import { CsrfTokenStore } from './CsrfTokenStore';

describe('CsrfTokenStore', () => {
    const token = 'abc123';
    const refreshFn = vi.fn();
    let store: CsrfTokenStore;
    let controller: AbortController;

    beforeEach(() => {
        controller = new AbortController();
        store = new CsrfTokenStore(null);
    });

    test('set and get token', async ({expect}) => {
        store.setToken(token);
        await expect(store.getToken(controller.signal)).resolves.toEqual(token)
    });

    test('token in constructor', async ({expect}) => {
        store = new CsrfTokenStore(token);
        await expect(store.getToken(controller.signal)).resolves.toEqual(token)
    });

    test('uses a refresh function', async ({expect}) => {
        refreshFn.mockImplementationOnce(async () => {
            store.setToken(token);
        });
        await expect(store.getToken(controller.signal, refreshFn)).resolves.toEqual(token)
        expect(refreshFn).toHaveBeenCalledTimes(1);
    });

    test('waits for a token', async ({expect}) => {
        const done = vi.fn();
        const prom = store.getToken(controller.signal);
        prom.then(done);
        expect(done).not.toHaveBeenCalled();
        store.setToken(token);
        await expect(prom).resolves.toEqual(token);
        expect(done).toHaveBeenCalledWith(token);
    });

    test('aborts waiting', async ({expect}) => {
        expect.assertions(1);
        setTimeout(() => controller.abort('abort reason'), 50);
        await expect(() => store.getToken(controller.signal)).rejects.toThrowError('abort reason');
    });
});