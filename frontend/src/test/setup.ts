import { cleanup } from '@testing-library/preact';
import { afterEach, beforeAll, beforeEach } from 'vitest';
import { installAllPolyfills } from './polyfills';
import fetchMock, { manageFetchMockGlobally } from '@fetch-mock/vitest';

const _GIT_HASH_ = '12345abcde';

declare global {
    interface Window {
        _GIT_HASH_: string;
    }
}

beforeAll(() => {
    Object.assign(fetchMock.config, {
        fallbackToNetwork: false,
        warnOnFallback: true,
    });
    fetchMock.mockGlobal();
    manageFetchMockGlobally();
});

beforeEach(() => {
    installAllPolyfills();
    window._GIT_HASH_ = _GIT_HASH_;
});

// runs a cleanup after each test case (e.g. clearing jsdom)
afterEach(() => {
    cleanup();
});