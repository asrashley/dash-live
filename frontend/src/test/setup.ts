import { cleanup } from '@testing-library/preact';
import { afterEach, beforeAll, beforeEach } from 'vitest';
import { installAllPolyfills } from './polyfills';
import fetchMock, { manageFetchMockGlobally } from '@fetch-mock/vitest';

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
});

// runs a cleanup after each test case (e.g. clearing jsdom)
afterEach(() => {
    cleanup();
});