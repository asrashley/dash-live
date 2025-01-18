import { createContext } from 'preact';
import log from 'loglevel';

import { routeMap, uiRouteMap} from '@dashlive/routemap';
import { CsrfTokenStore } from './CsrfTokenStore';
import { CsrfTokenCollection } from './types/CsrfTokenCollection';
import { AllManifests } from './types/AllManifests';
import { AllStreamsJson, AllStreamsResponse } from './types/AllStreams';
import { JWToken } from './types/JWToken';
import { MultiPeriodStream, MultiPeriodStreamJson } from './types/MultiPeriodStream';
import { DecoratedMultiPeriodStream } from "./types/DecoratedMultiPeriodStream";
import { MultiPeriodStreamSummary } from './types/MultiPeriodStreamSummary';
import { ContentRolesMap } from './types/ContentRolesMap';
import { ModifyMultiPeriodStreamJson, ModifyMultiPeriodStreamResponse } from './types/ModifyMultiPeriodStreamResponse';
import { InitialApiTokens } from './types/InitialApiTokens';
import { LoginRequest } from './types/LoginRequest';
import { LoginResponse } from './types/LoginResponse';
import { MultiPeriodStreamValidationRequest, MultiPeriodStreamValidationResponse } from './types/MpsValidation';
import { CgiOptionDescription } from './types/CgiOptionDescription';

type TokenStoreCollection = {
  files: CsrfTokenStore;
  kids: CsrfTokenStore;
  login: CsrfTokenStore;
  streams: CsrfTokenStore;
  upload: CsrfTokenStore;
};

export type ApiRequestOptions = {
  authorization?: string;
  body: RequestInit['body'];
  service: keyof TokenStoreCollection;
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

export interface ApiRequestsProps extends Readonly<InitialApiTokens> {
  navigate: (url: string) => void;
}

export class ApiRequests {
  private csrfTokens: TokenStoreCollection;
  private accessToken: JWToken | null;
  private refreshToken: JWToken | null;
  private navigate: ApiRequestsProps['navigate'];

  constructor({csrfTokens, accessToken, refreshToken, navigate}: ApiRequestsProps) {
    this.csrfTokens = {
      files: new CsrfTokenStore(csrfTokens?.files),
      kids: new CsrfTokenStore(csrfTokens?.kids),
      login: new CsrfTokenStore(csrfTokens?.login),
      streams: new CsrfTokenStore(csrfTokens?.streams),
      upload: new CsrfTokenStore(csrfTokens?.upload),
    }
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    this.navigate = navigate;
  }

  getAllManifests(options: Partial<ApiRequestOptions> = {}): Promise<AllManifests> {
    return this.sendApiRequest<AllManifests>(routeMap.listManifests.url(), options);
  }

  getContentRoles(options: Partial<ApiRequestOptions> = {}): Promise<ContentRolesMap> {
    return this.sendApiRequest(routeMap.contentRoles.url(), options);
  }

  getCgiOptions(options: Partial<ApiRequestOptions> = {}) : Promise<CgiOptionDescription[]> {
    return this.sendApiRequest(routeMap.cgiOptions.url(), options);
  }

  async getUserInfo(signal: AbortSignal): Promise<LoginResponse | Response> {
    if (!this.refreshToken) {
      throw new Error('Cannot get user info without a refresh token');
    }
    const options: Partial<ApiRequestOptions> = {
      authorization: this.refreshToken.jwt,
      method: 'GET',
      rejectOnError: false,
      signal,
    };
    const response = await this.sendApiRequest<LoginResponse | Response>(routeMap.login.url(), options);
    if (response['success']) {
      this.accessToken = (response as LoginResponse).accessToken;
    }
    return response;
  }

  async loginUser(request: LoginRequest, options: Partial<GetAllStreamsProps> = {}): Promise<LoginResponse> {
    const response: LoginResponse = await this.sendApiRequest<LoginResponse>(routeMap.login.url(), {
      body: JSON.stringify(request),
      method: 'POST',
      service: 'login',
      ...options,
    });
    if (response.success) {
      if (response.accessToken) {
        this.accessToken = response.accessToken;
      }
      if (response.refreshToken) {
        this.refreshToken = response.refreshToken;
      }
    }
    return response;
  }

  async logoutUser(options: Partial<GetAllStreamsProps> = {}): Promise<Response> {
    const response: Response = await this.sendApiRequest(routeMap.login.url(), {
      method: 'DELETE',
      service: 'login',
      ...options,
    });
    this.accessToken = null;
    this.refreshToken = null;
    return response;
  }

  async getAllStreams(options: Partial<GetAllStreamsProps> = {}): Promise<AllStreamsResponse> {
    const { streams, keys } = await this.sendApiRequest<AllStreamsJson>(routeMap.listStreams.url(), options);
    return { streams, keys};
  }

  getAllMultiPeriodStreams(options: Partial<ApiRequestOptions> = {}): Promise<MultiPeriodStreamSummary[]> {
    return this.sendApiRequest<MultiPeriodStreamSummary[]>(routeMap.listMps.url(), options);
  }

  async getMultiPeriodStream(mps_name: string, options: Partial<ApiRequestOptions> = {}): Promise<MultiPeriodStream> {
    const { model } = await this.sendApiRequest<MultiPeriodStreamJson>(routeMap.editMps.url({mps_name}), options);
    return model;
  }

  async addMultiPeriodStream(
      data: DecoratedMultiPeriodStream,
      options: Partial<ApiRequestOptions> = {}): Promise<ModifyMultiPeriodStreamResponse> {
    const service = 'streams';
    const csrf_token = await this.csrfTokens[service].getToken(
      options?.signal, this.getCsrfTokens);
    const { errors, success, model } = await this.sendApiRequest<ModifyMultiPeriodStreamJson>(routeMap.addMps.url(), {
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
    return await this.sendApiRequest<ModifyMultiPeriodStreamJson>(routeMap.editMps.url({mps_name}), {
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
    return this.sendApiRequest<Response>(routeMap.editMps.url({mps_name}), {
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
    return this.sendApiRequest<MultiPeriodStreamValidationResponse>(routeMap.validateMps.url(), {
      ...options,
      method: 'POST',
      service: 'streams',
      body: JSON.stringify({...data, csrf_token}),
    });
  }

  private async sendApiRequest<T>(url: string, options: Partial<ApiRequestOptions>): Promise<T> {
    const { authorization, body, service, signal, method='GET',
      rejectOnError = true } = options;
    let { query } = options;
    let usedAccessToken = false;
    const headers: Headers = new Headers({
      "Content-Type": "application/json",
    });
    if (authorization !== undefined) {
      headers.set('Authorization', `Bearer ${authorization}`);
    } else {
      if (!this.accessToken && this.refreshToken) {
        await this.getAccessToken(signal);
      }
      if (this.accessToken) {
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
    if (!this.refreshToken) {
      throw new Error('Cannot request an access token without a refresh token');
    }
    const options = {
      authorization: this.refreshToken.jwt,
      rejectOnError: false,
      signal,
    };
    const data = await this.sendApiRequest<RefreshAccessTokenResponse>(routeMap.refreshAccessToken.url(), options);
    const { accessToken, csrfTokens, ok, status } = data ?? {};
    if (ok === false && status === 401) {
      this.navigate(uiRouteMap.login.url());
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
