import log from 'loglevel';
import { routeMap } from './fixtures/routemap.js';
import { FakeEndpoint, HttpRequestHandler, jsonResponse, ServerRouteProps } from './FakeEndpoint'
import { ContentRolesMap } from '../types/ContentRolesMap';
import { CsrfTokenCollection } from '../types/CsrfTokenCollection';
import { JwtToken } from '../types/JwtToken';
import { AllMultiPeriodStreamsJson } from '../types/AllMultiPeriodStreams';

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
    refreshToken?: JwtToken;
    accessToken?: JwtToken;
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

export interface MockDashServerProps {
    endpoint: FakeEndpoint;
    accessTokenLifetime?: number;
    refreshTokenLifetime?: number;
};

export class MockDashServer {
    private endpoint: FakeEndpoint;
    private nextAccessTokenId = 1;
    private nextRefreshTokenId = 1000;
    private accessTokenLifetime: number;
    private refreshTokenLifetime: number;
    private userDatabase: UserModel[] = structuredClone([
        adminUser,
        normalUser,
        mediaUser,
    ]);

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
                    return 401;
                }
                if (group && !user.groups.includes(group)) {
                    log.trace(`user is not a member of group ${group}`);
                    return 401;
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
            .get(routeMap.listManifests.url(), this.returnSimpleFixture)
            .get(routeMap.contentRoles.url(), this.getContentRoles)
            .get(routeMap.listStreams.url(), this.returnSimpleFixture)
            .get(routeMap.listMps.url(), this.getAllMpStreams)
            .get(routeMap.editMps.url({mps_name: 'demo'}), this.returnSimpleFixture)
            .get(routeMap.refreshCsrfTokens.url(), protectedRoute(this.refreshCsrfTokens));
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
        delete user.password;
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
        });
    };

    private returnSimpleFixture = async (props: ServerRouteProps) => {
        const url = new URL(props.url, document.location.href);
        return jsonResponse(await this.endpoint.fetchFixtureJson<object>(
            `${url.pathname}.json`));
    };

    private getContentRoles = async () => {
        return jsonResponse(await this.endpoint.fetchFixtureJson<ContentRolesMap>('content_roles.json'));
    };

    private getAllMpStreams = async () => {
        return jsonResponse(await this.endpoint.fetchFixtureJson<AllMultiPeriodStreamsJson>(
            'multi-period-streams/index.json'));
    };

    //
    // helper functions
    //

    private getUserFromAccessToken({options}: ServerRouteProps): UserModel | undefined {
        const { headers } = options;
        if (!headers['authorization']) {
            log.trace('Request does not contain an Authorization header');
            return null;
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
