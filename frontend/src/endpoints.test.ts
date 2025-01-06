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
import { DecoratedMultiPeriodStream } from "./types/DecoratedMultiPeriodStream";
import { MpsPeriod } from "./types/MpsPeriod";

describe('endpoints', () => {
    const navigate = vi.fn();
    let endpoint: FakeEndpoint;
    let server: MockDashServer;
    let api: ApiRequests;
    let user: UserModel;

    beforeEach(() => {
        log.setLevel('error');
        endpoint = new FakeEndpoint(document.location.origin);
        server = new MockDashServer({
            endpoint
        });
        user = server.login(normalUser.email, normalUser.password);
        expect(user).not.toBeNull();
        const csrfTokens: CsrfTokenCollection = server.generateCsrfTokens(user);
        api = new ApiRequests({
            csrfTokens,
            navigate,
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
        const {streams} = await import('./test/fixtures/multi-period-streams/index.json');
        await expect(api.getAllMultiPeriodStreams()).resolves.toEqual({
            csrfTokens: expect.objectContaining({
                streams: expect.any(String),
            }),
            streams,
        });
    });

    test('get details of a multi-period stream', async () => {
        const demoMps = await import('./test/fixtures/multi-period-streams/demo.json');
        await expect(api.getMultiPeriodStream('demo')).resolves.toEqual(demoMps.default);
    });

    test('add a multi-period stream', async () => {
        const periods: MpsPeriod[] = [{
            parent: null,
            pid: 'p1',
            pk: 'p1',
            new: true,
            ordering: 1,
            stream: 5,
            start: "PT0S",
            duration: "PT30S",
            tracks: [],
        }];
        const newMps: DecoratedMultiPeriodStream = {
            pk: null,
            options: {},
            name: 'add-test',
            title: 'add a multi-period stream',
            modified: true,
            lastModified: 123,
            periods,
        };
        await expect(api.addMultiPeriodStream(newMps)).resolves.toEqual({
            model: newMps,
            success: true,
            errors: [],
            csrfTokens: expect.objectContaining({
                streams: expect.any(String),
            })
        });
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
            navigate,
            accessToken: user.accessToken,
            refreshToken: user.refreshToken,
        });
        await expect(api.getAllStreams()).resolves.toEqual(allStdStreams);
    });

    test('refreshes access token', async () => {
        const { username } = normalUser;
        expect(server.modifyUser({
            username,
            accessToken: null,
        })).toEqual(true);
        expect(server.getUser({username})?.accessToken).toBeNull();
        const csrfTokens: CsrfTokenCollection = server.generateCsrfTokens(user);
        api = new ApiRequests({
            csrfTokens,
            navigate,
            accessToken: null,
            refreshToken: user.refreshToken,
        });
        await expect(api.getAllStreams()).resolves.toEqual(allStdStreams);
        expect(server.getUser({username})?.accessToken).not.toBeNull();
    });

    test('refreshes both access token and CSRF tokens', async () => {
        const { username } = normalUser;
        const csrfTokens: CsrfTokenCollection = {
            files: null,
            kids: null,
            streams: null,
            upload: null,
        };
        api = new ApiRequests({
            csrfTokens,
            navigate,
            accessToken: null,
            refreshToken: user.refreshToken,
        });
        await expect(api.getAllStreams()).resolves.toEqual(allStdStreams);
        expect(server.getUser({username})?.accessToken).not.toBeNull();
    });

    test('generates error trying to refresh CSRF tokens without any JWT tokens', async () => {
        const csrfTokens: CsrfTokenCollection = {
            files: null,
            kids: null,
            streams: null,
            upload: null,
        };
        api = new ApiRequests({
            csrfTokens,
            navigate,
            accessToken: null,
            refreshToken: null,
        });
        await expect(api.getAllStreams()).rejects.toThrowError("Cannot request CSRF tokens");
    });

    test('generates error trying to refresh CSRF tokens with invalid refresh token', async () => {
        const csrfTokens: CsrfTokenCollection = {
            files: null,
            kids: null,
            streams: null,
            upload: null,
        };
        api = new ApiRequests({
            csrfTokens,
            navigate,
            accessToken: null,
            refreshToken: {
                expires: '2024-12-01T01:23:45Z',
                jti: 'abc123',
            },
        });
        await expect(api.getAllStreams()).rejects.toThrowError("Cannot request CSRF tokens");
        expect(navigate).toHaveBeenCalled();
        expect(navigate).toHaveBeenCalledWith('/login');
    });

});