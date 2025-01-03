import { cleanup } from '@testing-library/preact';
import { afterEach, beforeAll, beforeEach, vi } from 'vitest';
import fetchMock from 'fetch-mock';
import createFetchMock from 'vitest-fetch-mock';
import { installAllPolyfills } from './polyfills';

const fetchMocker = createFetchMock(vi);

beforeAll(() => {
    Object.assign(fetchMock.config, {
        fallbackToNetwork: false,
        warnOnFallback: true,
    });
    // sets globalThis.fetch and globalThis.fetchMock to our mocked version
    fetchMocker.enableMocks();
});

beforeEach(() => {
    installAllPolyfills();
});

// runs a cleanup after each test case (e.g. clearing jsdom)
afterEach(() => {
    cleanup();
});