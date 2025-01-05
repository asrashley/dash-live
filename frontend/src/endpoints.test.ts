import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import fetchMock from '@fetch-mock/vitest';
import log from 'loglevel';

import { MockDashServer, normalUser, UserModel } from "./test/MockServer";
import { ApiRequests } from "./endpoints";
import { CsrfTokenCollection } from "./types/CsrfTokenCollection";
import { FakeEndpoint } from "./test/FakeEndpoint";
import allManifests from './test/fixtures/manifests.json';
import contentRoles from './test/fixtures/content_roles.json';
import allStdStreams from './test/fixtures/streams.json';

describe('endpoints', () => {
    let endpoint: FakeEndpoint;
    //let server: MockDashServer;
    let api: ApiRequests;
    let user: UserModel;

    beforeEach(() => {
        log.setLevel('error');
        endpoint = new FakeEndpoint(document.location.origin);
        const server = new MockDashServer({
            endpoint
        });
        user = server.login(normalUser.email, normalUser.password);
        expect(user).not.toBeNull();
        const csrfTokens: CsrfTokenCollection = server.generateCsrfTokens(user);
        api = new ApiRequests({
            csrfTokens,
            accessToken: user.accessToken,
            refreshToken: user.refreshToken,
        });
    });

    afterEach(() => {
        endpoint.shutdown();
        vi.clearAllMocks();
        fetchMock.mockReset();
    });

    test('fetch manifest list', async () => {
        await expect(api.getAllManifests()).resolves.toEqual(allManifests);
    });

    test('get content roles', async () => {
        await expect(api.getContentRoles()).resolves.toEqual(contentRoles);
    });

    test('get all conventional streams', async () => {
        await expect(api.getAllStreams()).resolves.toEqual(allStdStreams);
    });

    test('get all multi-period streams', async () => {
        const allMpsStreams = await import('./test/fixtures/multi-period-streams/index.json');
        await expect(api.getAllMultiPeriodStreams()).resolves.toEqual(allMpsStreams.default);
    });

    test('get details of a multi-period stream', async () => {
        const demoMps = await import('./test/fixtures/multi-period-streams/demo.json');
        await expect(api.getMultiPeriodStream('demo')).resolves.toEqual(demoMps.default);
    });

    test('refreshes CSRF tokens', async () => {
        const csrfTokens: CsrfTokenCollection = {
            files: null,
            kids: null,
            streams: null,
            upload: null,
        };
        api = new ApiRequests({
            csrfTokens,
            accessToken: user.accessToken,
            refreshToken: user.refreshToken,
        });
        await expect(api.getAllStreams()).resolves.toEqual(allStdStreams);
    })
});