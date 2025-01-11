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
import { LoginRequest } from "./types/LoginRequest";

import { model as demoMps} from './test/fixtures/multi-period-streams/demo.json';
import { MultiPeriodStreamValidationRequest } from "./types/MpsValidation";

describe('endpoints', () => {
    const navigate = vi.fn();
    const noCsrfTokens: CsrfTokenCollection = {
        files: null,
        kids: null,
        login: null,
        streams: null,
        upload: null,
    };
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

    test.each(['username', 'email'])('can login using %s', async (field: string) => {
        const { email, username, password } = normalUser;
        const request: LoginRequest = {
            username: field === 'username' ? username : email,
            password,
            rememberme: false,
        };
        await expect(api.loginUser(request)).resolves.toEqual(expect.objectContaining({
            success: true,
            mustChange: false,
            csrf_token: expect.any(String),
            accessToken: {
                expires: expect.any(String),
                jti: expect.any(String),
            },
            refreshToken: {
                expires: expect.any(String),
                jti: expect.any(String),
            },
            user: {
                pk: normalUser.pk,
                email: normalUser.email,
                username: normalUser.username,
                groups: normalUser.groups,
                last_login: null,
                isAuthenticated: true,
            },
        }));
    });

    test('can login fails with unknown user', async () => {
        const { password } = normalUser;
        const request: LoginRequest = {
            username: 'not-a-user',
            password,
            rememberme: false,
        };
        await expect(api.loginUser(request)).resolves.toEqual(expect.objectContaining({
            success: false,
            error: "Wrong username or password",
        }));
    });

    test('can login fails with wrong password', async () => {
        const { username } = normalUser;
        const request: LoginRequest = {
            username,
            password: 'wrong!',
            rememberme: false,
        };
        await expect(api.loginUser(request)).resolves.toEqual(expect.objectContaining({
            success: false,
            error: "Wrong username or password",
        }));
    });

    test('get all conventional streams', async () => {
        await expect(api.getAllStreams()).resolves.toEqual(allStdStreams);
    });

    test('get all multi-period streams', async () => {
        const { streams } = await import('./test/fixtures/multi-period-streams/index.json');
        await expect(api.getAllMultiPeriodStreams()).resolves.toEqual({
            csrfTokens: expect.objectContaining({
                streams: expect.any(String),
            }),
            streams,
        });
    });

    test('get details of a multi-period stream', async () => {
        await expect(api.getMultiPeriodStream('demo')).resolves.toEqual({
            csrfTokens: {
                streams: expect.any(String),
            },
            model: demoMps,
        });
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

    test('modify a multi-period stream', async () => {
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
        const { pk, options, name } = demoMps;
        const newMps: DecoratedMultiPeriodStream = {
            pk,
            options,
            name,
            title: 'modify a multi-period stream',
            modified: true,
            lastModified: 123,
            periods,
        };
        await expect(api.modifyMultiPeriodStream(name, newMps)).resolves.toEqual({
            model: newMps,
            success: true,
            errors: [],
            csrfTokens: expect.objectContaining({
                streams: expect.any(String),
            })
        });
    });

    test('delete a multi-period stream', async () => {
        await expect(api.deleteMultiPeriodStream('demo')).resolves.toEqual(expect.objectContaining({
            status: 204,
        }));
    });

    test('validate name of a multi-period stream', async () => {
        const req: MultiPeriodStreamValidationRequest = {
            pk: null,
            name: '',
            title: 'a title',
        };
        await expect(api.validateMultiPeriodStream(req)).resolves.toEqual({
            errors: {
                name: 'a name is required'
            }
        });
    });

    test('duplicate name of a multi-period stream', async () => {
        const req: MultiPeriodStreamValidationRequest = {
            pk: null,
            name: demoMps.name,
            title: 'a title',
        };
        await expect(api.validateMultiPeriodStream(req)).resolves.toEqual({
            errors: {
                name: 'duplicate name "demo"'
            }
        });
    });

    test('validate title of a multi-period stream', async () => {
        const req: MultiPeriodStreamValidationRequest = {
            pk: demoMps.pk,
            name: 'demo',
            title: '',
        };
        await expect(api.validateMultiPeriodStream(req)).resolves.toEqual({
            errors: {
                title: 'a title is required'
            }
        });
    });

    test('refreshes CSRF tokens', async () => {
        api = new ApiRequests({
            csrfTokens: noCsrfTokens,
            navigate,
            accessToken: user.accessToken,
            refreshToken: user.refreshToken,
        });
        await expect(api.getAllStreams()).resolves.toEqual(allStdStreams);
    });

    test('gets an access token using a refresh token', async () => {
        const { username } = normalUser;
        expect(server.modifyUser({
            username,
            accessToken: null,
        })).toEqual(true);
        expect(server.getUser({ username })?.accessToken).toBeNull();
        const csrfTokens: CsrfTokenCollection = server.generateCsrfTokens(user);
        api = new ApiRequests({
            csrfTokens,
            navigate,
            accessToken: null,
            refreshToken: user.refreshToken,
        });
        await expect(api.getAllStreams()).resolves.toEqual(allStdStreams);
        expect(server.getUser({ username })?.accessToken).not.toBeNull();
    });

    test('refreshes an access token', async () => {
        const { username } = normalUser;
        expect(server.modifyUser({
            username,
            accessToken: {
                expires: '2024-12-01T01:02:03Z',
                jti: 'not.valid',
            },
        })).toEqual(true);
        const csrfTokens: CsrfTokenCollection = server.generateCsrfTokens(user);
        api = new ApiRequests({
            csrfTokens,
            navigate,
            accessToken: null,
            refreshToken: user.refreshToken,
        });
        await expect(api.getAllStreams()).resolves.toEqual(allStdStreams);
        expect(server.getUser({ username })?.accessToken).not.toBeNull();
    });

    test('refreshes both access token and CSRF tokens', async () => {
        const { username } = normalUser;
        api = new ApiRequests({
            csrfTokens: noCsrfTokens,
            navigate,
            accessToken: null,
            refreshToken: user.refreshToken,
        });
        await expect(api.getAllStreams()).resolves.toEqual(allStdStreams);
        expect(server.getUser({ username })?.accessToken).not.toBeNull();
    });

    test('generates error trying to refresh CSRF tokens without any JWT tokens', async () => {
        api = new ApiRequests({
            csrfTokens: noCsrfTokens,
            navigate,
            accessToken: null,
            refreshToken: null,
        });
        await expect(api.getAllStreams()).rejects.toThrowError("Cannot request CSRF tokens");
    });

    test('generates error trying to refresh CSRF tokens with invalid refresh token', async () => {
        api = new ApiRequests({
            csrfTokens: noCsrfTokens,
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