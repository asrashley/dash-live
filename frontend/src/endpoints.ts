import { createContext } from 'preact';
import log from 'loglevel';

import { routeMap } from '@dashlive/routemap';
import { CsrfTokenStore } from './CsrfTokenStore';
import { CsrfTokenCollection } from './types/CsrfTokenCollection';
import { AllManifests } from './types/AllManifests';
import { AllStreamsJson, AllStreamsResponse } from './types/AllStreams';
import { MultiPeriodStream, MultiPeriodStreamJson } from './types/MultiPeriodStream';
import { DecoratedMultiPeriodStream } from "./types/DecoratedMultiPeriodStream";
import { MultiPeriodStreamSummary } from './types/MultiPeriodStreamSummary';
import { ContentRolesMap } from './types/ContentRolesMap';
import { ModifyMultiPeriodStreamJson, ModifyMultiPeriodStreamResponse } from './types/ModifyMultiPeriodStreamResponse';
import { JWToken } from './user/types/JWToken';
import { LoginRequest } from './user/types/LoginRequest';
import { LoginResponse } from './user/types/LoginResponse';
import { InitialUserState } from './user/types/InitialUserState';
import { ModifyUserResponse } from './user/types/ModifyUserResponse';
import { EditUserState } from "./user/types/EditUserState";
import { MultiPeriodStreamValidationRequest, MultiPeriodStreamValidationResponse } from './types/MpsValidation';
import { CgiOptionDescription } from './types/CgiOptionDescription';
import { DashParameters } from './player/types/DashParameters';

type TokenStoreCollection = {
  files: CsrfTokenStore;
  kids: CsrfTokenStore;
  login: CsrfTokenStore;
  streams: CsrfTokenStore;
  upload: CsrfTokenStore;
};

export type ApiRequestOptions = {
  authorization?: string | null;
  body?: RequestInit['body'];
  service?: keyof TokenStoreCollection;
  signal?: AbortSignal;
  method: RequestInit['method'];
  rejectOnError?: boolean;
  query?: URLSearchParams;
};

export type GetAllStreamsProps = ApiRequestOptions & {
  withDetails: boolean
};

type RefreshAccessTokenResponse = {
  accessToken?: JWToken;
  csrfTokens: CsrfTokenCollection;
  ok: boolean;
  status: number;
};

export interface ApiRequestsProps {
  needsRefreshToken: () => void;
  hasUserInfo: (ius: InitialUserState | null) => void;
}

export class ApiRequests {
  private csrfTokens: TokenStoreCollection;
  private accessToken: JWToken | null = null;
  private refreshToken: JWToken | null = null;
  private refreshTokenNeedsCheck = false;
  private refreshTokenChecker?: PromiseWithResolvers<boolean>;
  private needsRefreshToken: ApiRequestsProps["needsRefreshToken"]
  private hasUserInfo: ApiRequestsProps["hasUserInfo"]

  constructor({ hasUserInfo, needsRefreshToken }: ApiRequestsProps) {
    this.csrfTokens = {
      files: new CsrfTokenStore(null),
      kids: new CsrfTokenStore(null),
      login: new CsrfTokenStore(null),
      streams: new CsrfTokenStore(null),
      upload: new CsrfTokenStore(null),
    }
    this.needsRefreshToken = needsRefreshToken;
    this.hasUserInfo = hasUserInfo;
  }

  setAccessToken(token: JWToken | null) {
    this.accessToken = token;
    if (token !== null) {
      this.refreshTokenNeedsCheck = false;
    }
  }

  setRefreshToken(token: JWToken | null) {
    const needsCheck = token !== null && token !== this.refreshToken;
    this.refreshToken = token;
    this.refreshTokenNeedsCheck = needsCheck;
    log.trace(`Set refresh token. Needs check: ${needsCheck}`);
  }

  async getAllManifests(options: Partial<ApiRequestOptions> = {}): Promise<AllManifests> {
    await this.isRefreshTokenValid();
    return await this.sendApiRequest<AllManifests>(routeMap.listManifests.url(), options);
  }

  async getContentRoles(options: Partial<ApiRequestOptions> = {}): Promise<ContentRolesMap> {
    await this.isRefreshTokenValid();
    return await this.sendApiRequest<ContentRolesMap>(routeMap.contentRoles.url(), options);
  }

  async getCgiOptions(options: Partial<ApiRequestOptions> = {}) : Promise<CgiOptionDescription[]> {
    await this.isRefreshTokenValid();
    return await this.sendApiRequest<CgiOptionDescription[]>(routeMap.cgiOptions.url(), options);
  }

  async getDashParameters(mode: string, stream: string, manifest: string, params: Readonly<URLSearchParams>,
                          options: Partial<ApiRequestOptions> = {}): Promise<DashParameters> {
    await this.isRefreshTokenValid();
    const url = routeMap.videoParameters.url({
      mode,
      stream,
      manifest
    });
    return await this.sendApiRequest<DashParameters>(`${url}?${params.toString()}`, options);
  }

  async getUserInfo(signal?: AbortSignal): Promise<LoginResponse | Response> {
    if (!this.refreshToken) {
      this.refreshTokenNeedsCheck = false;
      this.refreshTokenChecker?.reject(new Error('No refresh token'));
      return new Response('No refresh token', { status: 401});
    }
    const options: Partial<ApiRequestOptions> = {
      authorization: this.refreshToken.jwt,
      method: 'GET',
      rejectOnError: false,
      signal,
    };
    try {
      const response = await this.sendApiRequest<LoginResponse | Response>(routeMap.login.url(), options);
      if (response['success']) {
        const loginResp = (response as LoginResponse)
        this.accessToken = loginResp.accessToken;
        this.hasUserInfo(loginResp.user);
      } else {
        this.hasUserInfo(null);
      }
      this.refreshTokenChecker?.resolve(!!response['success']);
      return response;
    } catch(err) {
      this.refreshTokenChecker?.reject(err);
      if (signal?.aborted) {
        throw err;
      }
      console.error(err);
      return new Response(`${err}`, { status: 401 });
    } finally {
      this.refreshTokenNeedsCheck = false;
    }
  }

  async loginUser(request: LoginRequest, options: Partial<GetAllStreamsProps> = {}): Promise<LoginResponse> {
    this.refreshToken = null;
    this.refreshTokenNeedsCheck = true;
    const response: LoginResponse = await this.sendApiRequest<LoginResponse>(routeMap.login.url(), {
      body: JSON.stringify(request),
      method: 'POST',
      ...options,
    });
    if (response.success) {
      if (response.accessToken) {
        this.accessToken = response.accessToken;
      }
      if (response.refreshToken) {
        this.refreshToken = response.refreshToken;
      }
      this.hasUserInfo(response.user);
    }
    this.refreshTokenNeedsCheck = false;
    if (this.refreshTokenChecker === undefined) {
      this.refreshTokenChecker = Promise.withResolvers<boolean>();
    }
    this.refreshTokenChecker.resolve(response.success);
    return response;
  }

  async logoutUser(options: Partial<GetAllStreamsProps> = {}): Promise<Response> {
    if (!this.accessToken && this.refreshToken) {
      await this.getAccessToken(options.signal);
    }
    const response: Response = await this.sendApiRequest<Response>(routeMap.login.url(), {
      method: 'DELETE',
      rejectOnError: false,
      ...options,
    });
    this.accessToken = null;
    this.refreshToken = null;
    this.refreshTokenNeedsCheck = false;
    this.refreshTokenChecker?.reject(new Error('logged out'));
    this.refreshTokenChecker = undefined;
    this.hasUserInfo(null);
    return response;
  }

  async getAllUsers(options: Partial<GetAllStreamsProps> = {}): Promise<InitialUserState[]> {
    return await this.sendProtectedApiRequest<InitialUserState[]>(routeMap.listUsers.url(), options);
  }

  async addUser(user: EditUserState, options: Partial<GetAllStreamsProps> = {}): Promise<ModifyUserResponse> {
    return await this.sendProtectedApiRequest<ModifyUserResponse>(routeMap.listUsers.url(), {
      ...options,
      method: 'PUT',
      body: JSON.stringify(user),
    });
  }

  async editUser(user: EditUserState, options: Partial<GetAllStreamsProps> = {}): Promise<ModifyUserResponse> {
    return await this.sendProtectedApiRequest<ModifyUserResponse>(routeMap.editUser.url({ upk: user.pk }), {
      ...options,
      method: 'POST',
      body: JSON.stringify(user),
    });
  }

  async deleteUser(userPk: number, options: Partial<GetAllStreamsProps> = {}): Promise<Response> {
    return await this.sendProtectedApiRequest<Response>(routeMap.editUser.url({ upk: userPk }), {
      ...options,
      method: 'DELETE',
    });
  }

  async getAllStreams(options: Partial<GetAllStreamsProps> = {}): Promise<AllStreamsResponse> {
    await this.isRefreshTokenValid();
    const { streams, keys } = await this.sendApiRequest<AllStreamsJson>(routeMap.listStreams.url(), options);
    return { streams, keys};
  }

  async getAllMultiPeriodStreams(options: Partial<ApiRequestOptions> = {}): Promise<MultiPeriodStreamSummary[]> {
    await this.isRefreshTokenValid();
    return await this.sendApiRequest<MultiPeriodStreamSummary[]>(routeMap.listMps.url(), options);
  }

  async getMultiPeriodStream(mps_name: string, options: Partial<ApiRequestOptions> = {}): Promise<MultiPeriodStream> {
    const { model } = await this.sendProtectedApiRequest<MultiPeriodStreamJson>(routeMap.editMps.url({mps_name}), options);
    return model;
  }

  async addMultiPeriodStream(
      data: DecoratedMultiPeriodStream,
      options: Partial<ApiRequestOptions> = {}): Promise<ModifyMultiPeriodStreamResponse> {
    const service = 'streams';
    const csrf_token = await this.csrfTokens[service].getToken(
      options?.signal, this.getCsrfTokens);
    const { errors, success, model } = await this.sendProtectedApiRequest<ModifyMultiPeriodStreamJson>(routeMap.addMps.url(), {
      ...options,
      service,
      body: JSON.stringify({
        ...data,
        csrf_token
      }),
      method: 'PUT',
    });
    return { errors, success, model };
  }

  async modifyMultiPeriodStream(mps_name: string, data: DecoratedMultiPeriodStream,
     options: Partial<ApiRequestOptions> = {}): Promise<ModifyMultiPeriodStreamJson> {
    const service = 'streams';
    const csrf_token = await this.csrfTokens[service].getToken(
      options?.signal, this.getCsrfTokens);
    return await this.sendProtectedApiRequest<ModifyMultiPeriodStreamJson>(routeMap.editMps.url({mps_name}), {
      ...options,
      service,
      body: JSON.stringify({...data, csrf_token}),
      method: 'POST',
    });
  }

  async deleteMultiPeriodStream(mps_name: string, options: Partial<ApiRequestOptions> = {}): Promise<Response> {
    const service = 'streams';
    const csrf_token = await this.csrfTokens[service].getToken(
      options?.signal, this.getCsrfTokens
    );
    const query = new URLSearchParams({
      csrf_token,
    });
    return this.sendProtectedApiRequest<Response>(routeMap.editMps.url({mps_name}), {
      ...options,
      service,
      query,
      method: 'DELETE',
    });
  }

  async validateMultiPeriodStream(data: MultiPeriodStreamValidationRequest,
        options: Partial<ApiRequestOptions> = {}): Promise<MultiPeriodStreamValidationResponse> {
    const service = 'streams';
    const csrf_token = await this.csrfTokens[service].getToken(
      options?.signal, this.getCsrfTokens);
    return this.sendProtectedApiRequest<MultiPeriodStreamValidationResponse>(routeMap.validateMps.url(), {
      ...options,
      method: 'POST',
      service: 'streams',
      body: JSON.stringify({...data, csrf_token}),
    });
  }

  private async sendProtectedApiRequest<T>(url: string, options: Partial<ApiRequestOptions>): Promise<T> {
    let ok = await this.isRefreshTokenValid(options.signal);
    if (!ok && this.refreshToken === null) {
      await this.getAccessToken(options.signal);
      ok = this.accessToken !== null;
    }
    if (!ok && options.rejectOnError) {
      throw new Error('This API request needs an access token');
    }
    if (!this.accessToken && this.refreshToken) {
      await this.getAccessToken(options.signal);
    }
    return await this.sendApiRequest<T>(url, options);
  }

  private async isRefreshTokenValid(signal?: AbortSignal): Promise<boolean> {
    if (!this.refreshTokenNeedsCheck) {
      return this.refreshToken !== null;
    }
    if (this.refreshTokenChecker === undefined) {
      this.refreshTokenChecker = Promise.withResolvers<boolean>();
      this.getUserInfo(signal);
    }
    return await this.refreshTokenChecker.promise;
  }

  private async sendApiRequest<T>(url: string, options: Partial<ApiRequestOptions>): Promise<T> {
    const { authorization, body, service, signal, method='GET',
      rejectOnError = true } = options;
    let { query } = options;
    let usedAccessToken = false;
    const headers: Headers = new Headers({
      "Content-Type": "application/json",
    });
    if (typeof authorization === "string") {
      headers.set('Authorization', `Bearer ${authorization}`);
    } else if (authorization !== null && this.accessToken) {
        headers.set('Authorization', `Bearer ${this.accessToken.jwt}`);
        usedAccessToken = true;
    } else if (service) {
        const token = await this.csrfTokens[service].getToken(signal);
      if (query === undefined) {
          query = new URLSearchParams({csrf_token: token});
      } else {
          query.set('csrf_token', token);
      }
    }

    if (query) {
      url = `${url}?${query.toString()}`;
    }
    if (signal && signal.aborted) {
      throw signal.reason;
    }
    const cache = 'no-cache';
    const credentials = 'same-origin';
    const mode = 'same-origin';
    url = new URL(url, document.location.origin).href;
    log.trace(`sendApiRequest(${url})`);
    let fetchResult = await fetch(url, {
      cache,
      credentials,
      mode,
      body,
      headers,
      method,
      signal,
    });
    log.trace(`url=${url} status=${fetchResult.status} usedAccessToken=${usedAccessToken}`);
    if (fetchResult.status === 401 && usedAccessToken && this.refreshToken) {
      await this.getAccessToken(signal);
      headers.set('Authorization', `Bearer ${this.accessToken.jwt}`);
      log.trace(`retrying sendApiRequest(${url})`);
      fetchResult = await fetch(url, {
          cache,
          credentials,
          mode,
          body,
          headers,
          method,
          signal,
      });
    }
    if (!fetchResult.ok) {
      if (rejectOnError) {
        throw new Error(`${ url }: ${ fetchResult.status }`);
      } else {
        return fetchResult as T;
      }
    }
    if (fetchResult.status !== 200) {
      return fetchResult as T;
    }
    const data = await fetchResult.json();
    if (signal?.aborted) {
      throw signal.reason;
    }
    if (typeof(data?.csrfTokens) === "object") {
      this.updateCsrfTokens(data.csrfTokens);
    } else if(typeof(data?.csrf_tokens) === "object") {
      this.updateCsrfTokens(data.csrf_tokens);
    } else if (typeof(data?.csrf_token) === "string") {
      this.updateCsrfTokens({[service]: data.csrf_token});
    }

    return data as T;
  }

  private updateCsrfTokens(tokens: Partial<CsrfTokenCollection>) {
    for (const [key, value] of Object.entries(tokens)) {
      if (this.csrfTokens[key] === undefined) {
        this.csrfTokens[key] = new CsrfTokenStore(value);
      } else {
        this.csrfTokens[key].setToken(value);
      }
    }
  }

  private async getAccessToken(signal: AbortSignal): Promise<JWToken> {
    const options: ApiRequestOptions = {
      method: 'GET',
      authorization: this.refreshToken?.jwt || null,
      rejectOnError: false,
      signal,
    };
    const data = await this.sendApiRequest<RefreshAccessTokenResponse>(routeMap.refreshAccessToken.url(), options);
    const { accessToken, csrfTokens, ok, status } = data ?? {};
    if (ok === false && status === 401) {
      this.refreshToken = null;
      this.needsRefreshToken();
    }
    if (!accessToken) {
      throw new Error('Failed to refresh access token');
    }
    this.accessToken = accessToken;
    if (csrfTokens) {
      this.updateCsrfTokens(csrfTokens);
    }
    return accessToken;
  }

  private getCsrfTokens = async (signal: AbortSignal): Promise<void> => {
    if (!this.accessToken && this.refreshToken) {
      await this.getAccessToken(signal);
    }
    if (!this.accessToken) {
      throw new Error('Cannot request CSRF tokens without an access token');
    }
    const options = {
      authorization: this.accessToken.jwt,
      signal,
    };
    const data = await this.sendApiRequest<RefreshAccessTokenResponse>(routeMap.refreshCsrfTokens.url(), options);
    const { csrfTokens } = data ?? {};
    if (csrfTokens) {
      this.updateCsrfTokens(csrfTokens);
    }
  };
}

export const EndpointContext = createContext<ApiRequests>(null);
