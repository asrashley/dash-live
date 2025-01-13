import { Temporal } from "temporal-polyfill";

import log from 'loglevel';
import { routeMap } from './fixtures/routemap.js';
import { FakeEndpoint, HttpRequestHandler, jsonResponse, notFound, ServerRouteProps } from './FakeEndpoint'
import { ContentRolesMap } from '../types/ContentRolesMap';
import { CsrfTokenCollection } from '../types/CsrfTokenCollection';
import { JwtToken } from '../types/JwtToken';
import { AllMultiPeriodStreamsJson, MultiPeriodStreamSummary } from '../types/AllMultiPeriodStreams';
import { ModifyMultiPeriodStreamJson } from '../types/ModifyMultiPeriodStreamJson';
import { MultiPeriodStream, MultiPeriodStreamJson } from '../types/MultiPeriodStream';
import { LoginRequest } from "../types/LoginRequest";
import { LoginResponse } from "../types/LoginResponse";
import { MultiPeriodStreamValidationRequest, MultiPeriodStreamValidationResponse } from "../types/MpsValidation";

enum UserGroups {
    USER = "USER",
    MEDIA = "MEDIA",
    ADMIN = "ADMIN"
}

export type UserModel = {
    pk: number;
    username: string;
    email: string;
    password: string;
    mustChange: boolean;
    lastLogin: string | null;
    groups: UserGroups[];
    refreshToken: JwtToken | null;
    accessToken: JwtToken | null;
};

export const normalUser: UserModel = {
    pk: 100,
    username: 'user',
    email: 'a.user@example.local',
    password: 'mysecret',
    mustChange: false,
    lastLogin: null,
    groups: [UserGroups.USER],
    accessToken: null,
    refreshToken: null,
};

export const mediaUser: UserModel = {
    ...normalUser,
    pk: 101,
    username: 'mediamgr',
    email: 'media.manager@example.local',
    password: 'qwerty123',
    groups: [UserGroups.USER, UserGroups.MEDIA],
};

export const adminUser: UserModel = {
    ...normalUser,
    pk: 1,
    username: 'admin',
    email: 'admin@example.local',
    password: 'sup3r$ecret!',
    groups: [UserGroups.USER, UserGroups.MEDIA, UserGroups.ADMIN],
};

function randomToken(length: number): string {
    const chars = 'abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ_=+';
    let token = '';
    while (token.length < length) {
        const index = Math.floor(Math.random() * chars.length);
        token += chars[index];
    }
    return token;
}

type RequestContext = {
    currentUser?: UserModel;
};

type MultiPeriodStreamRequest = MultiPeriodStream & {
    csrf_token: string;
};

export interface MockDashServerProps {
    endpoint: FakeEndpoint;
    accessTokenLifetime?: number;
    refreshTokenLifetime?: number;
}

export class MockDashServer {
    private endpoint: FakeEndpoint;
    private nextAccessTokenId = 1;
    //private nextRefreshTokenId = 1000;
    private accessTokenLifetime: number;
    private refreshTokenLifetime: number;
    private userDatabase: UserModel[] = structuredClone([
        adminUser,
        normalUser,
        mediaUser,
    ]);
    private mpsStreams: MultiPeriodStream[] | undefined;

    constructor({
        endpoint,
        accessTokenLifetime = 2 * 3600_000, // 2 hours
        refreshTokenLifetime = 7 * 24 * 3600_000, // 7 days
    }: MockDashServerProps) {
        this.endpoint = endpoint;
        this.accessTokenLifetime = accessTokenLifetime;
        this.refreshTokenLifetime = refreshTokenLifetime;
        const protectedRoute = (next: HttpRequestHandler, group?: UserGroups) => {
            return (props: ServerRouteProps) => {
                const user = this.getUserFromAccessToken(props);
                if (!user) {
                    log.trace('failed to find user from access token');
                    return jsonResponse('', 401);
                }
                if (group && !user.groups.includes(group)) {
                    log.trace(`user is not a member of group ${group}`);
                    return jsonResponse('', 401);
                }
                const nextProps = {
                    ...props,
                    context: {
                        ...props.context,
                        currentUser: user,
                    }
                };
                return next(nextProps);
            };
        };
        endpoint
            .post(routeMap.login.url(), this.loginUser)
            .delete(routeMap.login.url(), protectedRoute(this.logoutUser))
            .get(routeMap.refreshCsrfTokens.url(), protectedRoute(this.refreshCsrfTokens))
            .get(routeMap.refreshAccessToken.url(), this.refreshAccessToken)
            .get(routeMap.listManifests.url(), this.returnSimpleFixture)
            .get(routeMap.contentRoles.url(), this.getContentRoles)
            .get(routeMap.listStreams.url(), this.returnSimpleFixture)
            .get(routeMap.listMps.url(), protectedRoute(this.getAllMpStreams))
            .get(routeMap.editMps.re, protectedRoute(this.returnSimpleFixture))
            .put(routeMap.addMps.url(), protectedRoute(this.addMultiPeriodStream))
            .post(routeMap.editMps.re, protectedRoute(this.editMultiPeriodStream))
            .delete(routeMap.editMps.re, protectedRoute(this.deleteMultiPeriodStream))
            .post(routeMap.validateMps.url(), protectedRoute(this.validateMultiPeriodStream));
    }

    addUser(user: UserModel) {
        this.userDatabase.push(user);
    }

    login(username: string, password: string): UserModel | null {
        log.trace(`login ${username}`);
        const dbEntry = this.getUser({email: username, username});
        if (!dbEntry) {
            log.debug(`Failed to find user "${username}"`);
            return null;
        }
        if (dbEntry.password !== password) {
            log.debug(`Incorrect password for user "${username}"`);
            return null;
        }
        const user: UserModel = {
            ...normalUser,
            ...dbEntry,
            refreshToken: this.generateRefreshToken(dbEntry.username),
            accessToken: this.generateAccessToken(dbEntry.username),
        };
        this.userDatabase = this.userDatabase.map(usr => {
            if (usr.pk === user.pk) {
                return user;
            }
            return usr;
        });
        return user;
    }

    getUser({ email, username }: Partial<UserModel>): UserModel | undefined {
        return this.userDatabase.find(usr => usr.username === username || usr.email === email);
    }

    modifyUser(props: Partial<UserModel>): boolean {
        const { email, username } = props;
        const curUser = this.userDatabase.find(usr => usr.username === username || usr.email === email);
        if (!curUser) {
            return false;
        }
        this.userDatabase = this.userDatabase.map(user => {
            if (user.pk === curUser.pk) {
                return {
                    ...user,
                    ...props,
                };
            }
            return user;
        });
        return true;
    }

    isLoggedIn({ email, username }: Partial<UserModel>): boolean {
        const user = this.getUser({ email, username });
        return user && user.accessToken !== null;
    }

    generateCsrfTokens(user: UserModel): CsrfTokenCollection {
        const media = user.groups.includes(UserGroups.MEDIA);
        const csrfTokens: CsrfTokenCollection = {
            files: media ? `${user.username}.${randomToken(12)}` : null,
            kids: media ? `${user.username}.${randomToken(12)}` : null,
            streams: `${user.username}.${randomToken(12)}`,
            upload: null,
         };
         return csrfTokens;
    }

    //
    // JSON REST API
    //
    private loginUser = async ({jsonParam}: ServerRouteProps) => {
        if (!jsonParam) {
            return jsonResponse('', 400);
        }
        const { username, password } = jsonParam as LoginRequest;
        log.trace('login', username, password);
        const user = this.userDatabase.find(usr => (usr.username === username || usr.email === username) && usr.password === password);
        if (!user) {
            const result: LoginResponse = {
                success: false,
                error: "Wrong username or password",
                csrf_token: randomToken(12),
            };
            return jsonResponse(result);
        }
        const result: LoginResponse = {
            success: true,
            mustChange: user.mustChange,
            csrf_token: `${user.username}.${randomToken(12)}`,
            accessToken: this.generateAccessToken(user.username),
            refreshToken: this.generateRefreshToken(user.username),
            user: {
                pk: user.pk,
                email: user.email,
                username: user.username,
                groups: user.groups,
                last_login: user.lastLogin,
                isAuthenticated: true,
            }
        };
        user.lastLogin = new Date().toISOString();
        return jsonResponse(result);
    };

    private logoutUser = async ({context}: ServerRouteProps) => {
        const { currentUser } = context as RequestContext;
        this.userDatabase = this.userDatabase.map(user => {
            if (user.pk !== currentUser.pk) {
                return user;
            }
            return {
                ...user,
                accessToken: undefined,
                refreshToken: undefined,
            };
        });
        return jsonResponse('', 204);
    };

    private refreshCsrfTokens = async ({ context }: ServerRouteProps) => {
        const { currentUser } = context as RequestContext;
        return jsonResponse({csrfTokens: this.generateCsrfTokens(currentUser)});
    };

    private refreshAccessToken = async ({ options}: ServerRouteProps) => {
        const { headers } = options;
        if (!headers['authorization']) {
            return jsonResponse('Missing Authorization header', 401);
        }
        const token = (headers['authorization'] as string).split(' ')[1];
        const user = this.userDatabase.find(usr => usr.refreshToken?.jti === token);
        if (!user) {
            return jsonResponse('Refresh token mismatch', 401);
        }
        user.accessToken = this.generateAccessToken(user.username);
        return jsonResponse({
            accessToken: user.accessToken,
            csrfTokens: this.generateCsrfTokens(user),
        });
    };

    private returnSimpleFixture = async (props: ServerRouteProps) => {
        const url = new URL(props.url, document.location.href);
        const filename = url.pathname.replace("/api", "");
        return jsonResponse(await this.endpoint.fetchFixtureJson<object>(`${filename}.json`));
    };

    private getContentRoles = async () => {
        return jsonResponse(await this.endpoint.fetchFixtureJson<ContentRolesMap>('content_roles.json'));
    };

    private getAllMpStreams = async ({context}: ServerRouteProps) => {
        const mpStreams = await this.getMpsStreams();
        const result: AllMultiPeriodStreamsJson = {
            streams: mpStreams.map(createMpsSummary),
            csrfTokens: this.generateCsrfTokens((context as RequestContext).currentUser),
        };
        return jsonResponse(result);
    };

    private addMultiPeriodStream = async ({context, jsonParam}: ServerRouteProps) => {
        if (!jsonParam) {
            return jsonResponse('', 400);
        }
        if (this.mpsStreams === undefined) {
            await this.getMpsStreams();
        }
        const {csrf_token, ...mps} = jsonParam as MultiPeriodStreamRequest;
        if (!csrf_token) {
            return jsonResponse('CSRF token missing', 401);
        }
        this.mpsStreams.push(mps);
        const result: ModifyMultiPeriodStreamJson = {
            csrfTokens: {
                streams: `${(context as RequestContext).currentUser.username}.${randomToken(12)}`,
            },
            model: mps,
            success: true,
            errors: [],
        };
        return jsonResponse(result);
    };

    private editMultiPeriodStream = async ({ routeParams={}, context, jsonParam }: ServerRouteProps) => {
        const { mps_name } = routeParams;
        if (!mps_name) {
            return notFound();
        }
        if (!jsonParam) {
            return jsonResponse('', 400);
        }
        const allMps = await this.getMpsStreams();
        const mps = allMps.find(m => m.name === mps_name);
        if (!mps) {
            return notFound();
        }
        const { csrf_token, ...newMps } = jsonParam as MultiPeriodStreamRequest;
        if (!csrf_token) {
            return jsonResponse('', 401);
        }
        this.mpsStreams = this.mpsStreams.map((mp) => {
            if (mp.pk === mps.pk) {
                return newMps;
            }
            return mp;
        });
        const result: ModifyMultiPeriodStreamJson = {
            csrfTokens: {
                streams: `${(context as RequestContext).currentUser.username}.${randomToken(12)}`,
            },
            model: newMps,
            success: true,
            errors: [],
        };
        return jsonResponse(result);
    };

    private deleteMultiPeriodStream = async ({ routeParams={} }: ServerRouteProps) => {
        const { mps_name } = routeParams;
        if (!mps_name) {
            return notFound();
        }
        const allMps = await this.getMpsStreams();
        const mps = allMps.find(m => m.name === mps_name);
        if (!mps) {
            return notFound();
        }
        this.mpsStreams = this.mpsStreams.filter(m => m !== mps);
        return jsonResponse('', 204);
    };

    private validateMultiPeriodStream = async ({jsonParam}: ServerRouteProps) => {
        const req = jsonParam as MultiPeriodStreamValidationRequest;
        if (!req) {
            return jsonResponse('', 400);
        }
        const allMps = await this.getMpsStreams();
        const resp: MultiPeriodStreamValidationResponse = {
            errors: {}
        };
        if (req.name === "") {
            resp.errors.name = 'a name is required';
        } else if (allMps.some(m => m.name === req.name && m.pk !== req.pk)) {
            resp.errors.name = `duplicate name "${req.name}"`;
        }
        if (req.title === "") {
            resp.errors.title = 'a title is required';
        }
        return jsonResponse(resp);
    };

    //
    // helper functions
    //

    private async getMpsStreams() {
        if (this.mpsStreams === undefined) {
            const { streams } = await this.endpoint.fetchFixtureJson<AllMultiPeriodStreamsJson>(
                'multi-period-streams/index.json');
            const mpsStreams = [];
            for (const item of streams) {
                const {model} = await this.endpoint.fetchFixtureJson<MultiPeriodStreamJson>(
                    `multi-period-streams/${item.name}.json`
                );
                mpsStreams.push(model);
            }
            this.mpsStreams = mpsStreams;
        }
        return this.mpsStreams;
    }

    private getUserFromAccessToken({options}: ServerRouteProps): UserModel | undefined {
        const { headers } = options;
        if (!headers['authorization']) {
            log.trace('Request does not contain an Authorization header');
            return undefined;
        }
        const token = (headers['authorization'] as string).split(' ')[1];
        const user = this.userDatabase.find(usr => usr.accessToken?.jti === token);
        return user;
    }

    private findUser({ pk, username, email }: Partial<UserModel>): UserModel | undefined {
        return this.userDatabase.find(user => {
            if (pk && pk !== user.pk) {
                return false;
            }
            if (username && username !== user.username) {
                return false;
            }
            if (email && email !== user.email) {
                return false;
            }
            return true;
        });
    }

    private generateAccessToken(username: string): JwtToken {
        const expires = new Date(Date.now() + this.accessTokenLifetime).toISOString();
        return {
            expires,
            jti: `access.${username}.${this.nextAccessTokenId++}`,
        };
    }

    private generateRefreshToken(username: string): JwtToken {
        const expires = new Date(Date.now() + this.refreshTokenLifetime).toISOString();
        return {
            expires,
            jti: `refresh.${username}.${this.nextAccessTokenId++}`,
        };
    }
}

function createMpsSummary(mps: MultiPeriodStream): MultiPeriodStreamSummary {
    const { name, options, title, pk } = mps;
    const periods: number[] = mps.periods.map((prd, idx) => {
        if (typeof prd.pk === 'number') {
            return prd.pk;
        }
        return 100 + idx;
    });
    let duration: Temporal.Duration = new Temporal.Duration();
    for (const prd of mps.periods){
      const dur = Temporal.Duration.from(prd.duration);
      duration = duration.add(dur);
    }
    const summary: MultiPeriodStreamSummary = {
        name,
        duration: duration.toString(),
        options,
        periods,
        pk,
        title
    };
    return summary;
}

