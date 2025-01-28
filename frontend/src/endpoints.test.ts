import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import fetchMock from '@fetch-mock/vitest';
import { type RouteResponse } from "fetch-mock";
import log from 'loglevel';

import { routeMap } from "@dashlive/routemap";

import { adminUser, guestUser, mediaUser, MockDashServer, normalUser, UserModel, userToInitialState } from "./test/MockServer";
import { FakeEndpoint, HttpRequestHandlerResponse, ServerRouteProps } from "./test/FakeEndpoint";
import { ApiRequests } from "./endpoints";
import { DecoratedMultiPeriodStream } from "./types/DecoratedMultiPeriodStream";
import { MpsPeriod } from "./types/MpsPeriod";
import { LoginRequest } from "./types/LoginRequest";
import { MultiPeriodStreamValidationRequest } from "./types/MpsValidation";

import allManifests from './test/fixtures/manifests.json';
import contentRoles from './test/fixtures/content_roles.json';
import allStdStreams from './test/fixtures/streams.json';
import { model as demoMps } from './test/fixtures/multi-period-streams/demo.json';
import cgiOptions from './test/fixtures/cgiOptions.json';
import { InitialUserState } from "./types/UserState";
import { EditUserState } from "./hooks/useAllUsers";

describe('endpoints', () => {
    const needsRefreshToken = vi.fn();
    const hasUserInfo = vi.fn();
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
        api = new ApiRequests({
            hasUserInfo,
            needsRefreshToken,
        });
    });

    afterEach(() => {
        endpoint.shutdown();
        vi.clearAllMocks();
        fetchMock.mockReset();
    });

    test('fetch manifest list', async () => {
        await expect(api.getAllManifests()).resolves.toEqual(allManifests);
        expect(hasUserInfo).not.toHaveBeenCalled();
        expect(needsRefreshToken).not.toHaveBeenCalled();
    });

    test('get content roles', async () => {
        await expect(api.getContentRoles()).resolves.toEqual(contentRoles);
        expect(hasUserInfo).not.toHaveBeenCalled();
        expect(needsRefreshToken).not.toHaveBeenCalled();
    });

    test('get cgi options', async () => {
        await expect(api.getCgiOptions()).resolves.toEqual(cgiOptions);
        expect(hasUserInfo).not.toHaveBeenCalled();
        expect(needsRefreshToken).not.toHaveBeenCalled();
    });

    test.each(['username', 'email'])('can login using %s', async (field: string) => {
        const { email, username, password } = normalUser;
        const request: LoginRequest = {
            username: field === 'username' ? username : email,
            password,
            rememberme: false,
        };
        const user: InitialUserState = {
            pk: normalUser.pk,
            email: normalUser.email,
            username: normalUser.username,
            groups: normalUser.groups,
            lastLogin: null,
            mustChange: false,
        };
        await expect(api.loginUser(request)).resolves.toEqual(expect.objectContaining({
            success: true,
            csrf_token: expect.any(String),
            accessToken: {
                expires: expect.any(String),
                jwt: expect.any(String),
            },
            refreshToken: {
                expires: expect.any(String),
                jwt: expect.any(String),
            },
            user,
        }));
        expect(hasUserInfo).toHaveBeenCalledTimes(1);
        expect(hasUserInfo).toHaveBeenCalledWith(user);
        expect(needsRefreshToken).not.toHaveBeenCalled();
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

    test('can log out with a valid access token', async () => {
        api.setRefreshToken(user.refreshToken);
        api.setAccessToken(user.accessToken);
        await expect(api.logoutUser()).resolves.toEqual(expect.objectContaining({
            status: 204,
        }));
        user = server.getUser(normalUser);
        expect(user).toBeDefined();
        expect(user.accessToken).toBeUndefined();
        expect(user.refreshToken).toBeUndefined();
        expect(hasUserInfo).toHaveBeenCalledTimes(1);
        expect(hasUserInfo).toHaveBeenCalledWith(null);
    });

    test('can log out with a no access token + valid refresh token', async () => {
        api.setRefreshToken(user.refreshToken);
        await expect(api.logoutUser()).resolves.toEqual(expect.objectContaining({
            status: 204,
        }));
        user = server.getUser(normalUser);
        expect(user).toBeDefined();
        expect(user.accessToken).toBeUndefined();
        expect(user.refreshToken).toBeUndefined();
        expect(hasUserInfo).toHaveBeenCalledTimes(1);
        expect(hasUserInfo).toHaveBeenCalledWith(null);
    });

    test('log out without a refresh token', async () => {
        await expect(api.logoutUser()).resolves.toEqual(expect.objectContaining({
            status: 401,
        }));
        expect(hasUserInfo).toHaveBeenCalledTimes(1);
        expect(hasUserInfo).toHaveBeenCalledWith(null);
    });

    test('get all conventional streams', async () => {
        const { keys, streams } = allStdStreams;
        await expect(api.getAllStreams()).resolves.toEqual({ keys, streams });
    });

    test('get all multi-period streams', async () => {
        const streams = await import('./test/fixtures/multi-period-streams/index.json');
        await expect(api.getAllMultiPeriodStreams()).resolves.toEqual(streams.default);
    });

    test('get details of a multi-period stream', async () => {
        api.setRefreshToken(user.refreshToken);
        api.setAccessToken(user.accessToken);
        await expect(api.getMultiPeriodStream('demo')).resolves.toEqual(demoMps);
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
        api.setRefreshToken(user.refreshToken);
        api.setAccessToken(user.accessToken);
        await expect(api.addMultiPeriodStream(newMps)).resolves.toEqual({
            model: newMps,
            success: true,
            errors: [],
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
        api.setRefreshToken(user.refreshToken);
        api.setAccessToken(user.accessToken);
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
        api.setRefreshToken(user.refreshToken);
        api.setAccessToken(user.accessToken);
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
        api.setRefreshToken(user.refreshToken);
        api.setAccessToken(user.accessToken);
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
        api.setRefreshToken(user.refreshToken);
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
        api.setRefreshToken(user.refreshToken);
        await expect(api.validateMultiPeriodStream(req)).resolves.toEqual({
            errors: {
                title: 'a title is required'
            }
        });
    });

    test('refreshes CSRF tokens', async () => {
        const { keys, streams } = allStdStreams;
        api.setRefreshToken(user.refreshToken);
        await expect(api.getAllStreams()).resolves.toEqual({ keys, streams });
    });

    test('gets an access token using a refresh token', async () => {
        const { username } = normalUser;
        expect(server.modifyUser({
            username,
            accessToken: null,
        })).toEqual(true);
        expect(server.getUser({ username })?.accessToken).toBeNull();
        api.setRefreshToken(user.refreshToken);
        const prom = endpoint.addResponsePromise('get', routeMap.refreshAccessToken.url());
        await expect(api.getMultiPeriodStream('demo')).resolves.toEqual(demoMps);
        const response: RouteResponse = await prom;
        expect(response).toEqual(expect.objectContaining({
            status: 200,
            body: expect.any(String),
        }));
        const body = JSON.parse(response['body']);
        expect(body).toEqual(expect.objectContaining({
            accessToken: {
                expires: expect.any(String),
                jwt: expect.any(String),
            },
        }));
        expect(server.getUser({ username })?.accessToken).not.toBeNull();
    });

    test('gets a guest access token when there is no refresh token', async () => {
        api.setRefreshToken(null);
        const prom = endpoint.addResponsePromise('get', routeMap.refreshAccessToken.url());
        await expect(api.getMultiPeriodStream('demo')).resolves.toEqual(demoMps);
        const response: RouteResponse = await prom;
        expect(response).toEqual(expect.objectContaining({
            status: 200,
            body: expect.any(String),
        }));
        const body = JSON.parse(response['body']);
        const user = server.getUser({ username: guestUser.username });
        expect(user).toBeDefined();
        expect(body).toEqual(expect.objectContaining({
            accessToken: user?.accessToken,
        }));
    });

    test('refreshes an access token', async () => {
        const { username } = normalUser;
        api.setRefreshToken(user.refreshToken);
        api.setAccessToken({
            expires: '2024-12-01T01:02:03Z',
            jwt: 'not.valid',
        });
        await expect(api.getMultiPeriodStream('demo')).resolves.toEqual(demoMps);
        expect(server.getUser({ username })?.accessToken).toBeDefined();
        expect(server.getUser({ username })?.accessToken.jwt).not.toEqual('not.valid');
    });

    test('refreshes both access token and CSRF tokens', async () => {
        const { username } = normalUser;
        api.setRefreshToken(user.refreshToken);
        api.setAccessToken(null);
        await expect(api.getMultiPeriodStream('demo')).resolves.toEqual(demoMps);
        expect(server.getUser({ username })?.accessToken).not.toBeNull();
    });

    test('generates error trying to refresh CSRF tokens with invalid refresh token', async () => {
        api.setRefreshToken({
            expires: '2024-12-01T01:23:45Z',
            jwt: 'abc123',
        });
        await expect(api.getMultiPeriodStream('demo')).rejects.toThrowError("Failed to refresh access token");
        expect(needsRefreshToken).toHaveBeenCalledTimes(1);
    });

    test('can abort a request', async () => {
        const controller = new AbortController();
        const { promise, resolve } = Promise.withResolvers<void>();
        endpoint.setResponseModifier(
            'get',
            routeMap.listManifests.url(),
            async (_props: ServerRouteProps, response: HttpRequestHandlerResponse) => {
                await promise;
                return response;
            }
        );
        controller.abort("abort the request");
        resolve();
        await expect(api.getAllManifests({ signal: controller.signal })).rejects.toThrow("abort the request");
    });

    test('can abort after refreshing an access token', async () => {
        const controller = new AbortController();
        const { username } = user;
        const url: string = routeMap.editMps.url({ mps_name: "demo" });
        api.setRefreshToken(user.refreshToken);
        api.setAccessToken({
            expires: '2024-12-01T01:02:03Z',
            jwt: 'not.valid',
        });
        const responseSpy = vi.fn();
        endpoint.setResponseModifier('get', url, responseSpy);
        responseSpy.mockImplementationOnce(async (_props: ServerRouteProps, response: HttpRequestHandlerResponse) => {
            controller.abort("abort request");
            return response;
        });
        await expect(api.getMultiPeriodStream('demo', { signal: controller.signal })).rejects.toThrow("aborted");
        expect(responseSpy).toHaveBeenCalledTimes(1);
        expect(server.getUser({ username })?.accessToken).toBeDefined();
        expect(server.getUser({ username })?.accessToken.jwt).not.toEqual('not.valid');
    });

    test('get list of all users fails for non-admin user', async () => {
        api.setRefreshToken(user.refreshToken);
        await expect(api.getAllUsers()).rejects.toThrow('401');
    });

    test('get list of all users as admin user', async () => {
        user = server.login(adminUser.email, adminUser.password);
        expect(user).not.toBeNull();
        api.setRefreshToken(user.refreshToken);
        const userList: InitialUserState[] = [
            userToInitialState(normalUser),
            userToInitialState(mediaUser),
            userToInitialState(adminUser),
        ];
        userList.sort((a, b) => a.pk - b.pk);
        await expect(api.getAllUsers()).resolves.toEqual(userList);
    });

    test('add a new user', async () => {
        user = server.login(adminUser.email, adminUser.password);
        expect(user).not.toBeNull();
        api.setRefreshToken(user.refreshToken);
        const newUser: EditUserState = {
            username: 'newUser',
            email: 'add.test@localhost',
            password: 'qwerty',
            confirmPassword: 'qwerty',
            mustChange: true,
            userGroup: true,
            mediaGroup: false,
            adminGroup: false,
            lastLogin: null,
        };
        const { username, email, mustChange } = newUser;
        const expectedUser: InitialUserState = {
            pk: expect.any(Number),
            username,
            email,
            mustChange,
            groups: ['USER'],
            lastLogin: null,
        };
        await expect(api.addUser(newUser)).resolves.toEqual({
            errors: [],
            success: true,
            user: expectedUser,
        });
        expect(server.getUser({ username })).toBeDefined();
    });

    test('delete a user', async () => {
        user = server.login(adminUser.email, adminUser.password);
        expect(user).not.toBeNull();
        api.setRefreshToken(user.refreshToken);
        await expect(api.deleteUser(normalUser.pk)).resolves.toEqual(expect.objectContaining({
            status: 204,
        }));
    });

    test('delete a user that does not exist', async () => {
        user = server.login(adminUser.email, adminUser.password);
        expect(user).not.toBeNull();
        api.setRefreshToken(user.refreshToken);
        await expect(api.deleteUser(5000)).rejects.toThrow('404');
    });

});