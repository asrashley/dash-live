import { createContext } from 'preact';
import { routeMap } from '@dashlive/routemap';
import { type RouteMap } from './types/RouteMap';
import { CsrfTokenStore } from './CsrfTokenStore';
import { CsrfTokenCollection } from './types/CsrfTokenCollection';
import { AllManifests } from './types/AllManifests';
import { AllStreamsJson } from './types/AllStreams';
import { JwtToken } from './types/JwtToken';
import { DecoratedMultiPeriodStream, MultiPeriodStreamJson } from './types/MultiPeriodStream';

type TokenStoreCollection = {
  files: CsrfTokenStore;
  kids: CsrfTokenStore;
  streams: CsrfTokenStore;
  upload: CsrfTokenStore;
};

export type ApiRequestOptions = {
  authorization?: string;
  body: RequestInit['body'];
  service: 'streams' | 'files' | 'kids' | 'upload';
  signal?: AbortSignal;
  method: RequestInit['method'];
  rejectOnError?: boolean;
  query?: URLSearchParams;
};

export type GetAllStreamsProps = ApiRequestOptions & {
  withDetails: boolean
};

type RefreshAccessTokenResponse = {
  accessToken?: JwtToken;
  csrfTokens: CsrfTokenCollection;
  ok: boolean;
  status: number;
};

export interface ApiRequestsProps {
  csrfTokens: Partial<CsrfTokenCollection>;
  accessToken: JwtToken | null;
  refreshToken: JwtToken | null;
}
export class ApiRequests {
  private csrfTokens: TokenStoreCollection;
  private accessToken: JwtToken | null;
  private refreshToken: JwtToken | null;

  constructor({csrfTokens, accessToken, refreshToken}: ApiRequestsProps) {
    this.csrfTokens = {
      files: new CsrfTokenStore(csrfTokens?.files),
      kids: new CsrfTokenStore(csrfTokens?.kids),
      streams: new CsrfTokenStore(csrfTokens?.streams),
      upload: new CsrfTokenStore(csrfTokens?.upload),
    }
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
  }

  getAllManifests(options: Partial<ApiRequestOptions> = {}): Promise<AllManifests> {
    return this.sendApiRequest(routeMap.listManifests.url(), options);
  }

  async getAllStreams({ withDetails = false, ...options}: Partial<GetAllStreamsProps>  = {}): Promise<AllStreamsJson> {
    const service = 'streams';
    const csrf_token = await this.csrfTokens[service].getToken(
      options?.signal, this.getCsrfTokens);
    const query = new URLSearchParams({
      details: withDetails ? "1" : "0",
      csrf_token,
    });
    return await this.sendApiRequest(routeMap.listStreams.url(), {
      service,
      query,
      ...options,
    });
  }

  async getAllMultiPeriodStreams(options: Partial<ApiRequestOptions> = {}): Promise<MultiPeriodStreamJson> {
    const service = 'streams';
    const csrf_token = await this.csrfTokens[service].getToken(
      options?.signal, this.getCsrfTokens);
    const query = new URLSearchParams({
      csrf_token,
    });
    return await this.sendApiRequest(routeMap.listMps.url(), {
      service,
      query,
      ...options,
    });
  }

  async getMultiPeriodStream(mps_name: string, options: Partial<ApiRequestOptions> = {}): Promise<MultiPeriodStreamJson> {
    const service = 'streams';
    const csrf_token = await this.csrfTokens[service].getToken(
      options?.signal, this.getCsrfTokens);
    const query = new URLSearchParams({
      csrf_token,
    });
    return await this.sendApiRequest(routeMap.editMps.url({mps_name}), {
      service,
      query,
      ...options,
    });
  }

  async addMultiPeriodStream(data: DecoratedMultiPeriodStream, options: Partial<ApiRequestOptions> = {}) {
    const service = 'streams';
    const csrf_token = await this.csrfTokens[service].getToken(
      options?.signal, this.getCsrfTokens);
    return await this.sendApiRequest(routeMap.addMps.url(), {
      ...options,
      service,
      body: JSON.stringify({
        ...data,
        csrf_token
      }),
      method: 'PUT',
    });
  }

  async modifyMultiPeriodStream(mps_name: string, data: DecoratedMultiPeriodStream, options: Partial<ApiRequestOptions> = {}) {
    const service = 'streams';
    const csrf_token = await this.csrfTokens[service].getToken(
      options?.signal, this.getCsrfTokens);
    return await this.sendApiRequest(routeMap.editMps.url({mps_name}), {
      ...options,
      service,
      body: JSON.stringify({...data, csrf_token}),
      method: 'POST',
    });
  }

  async deleteMultiPeriodStream(mps_name, options) {
    const service = 'streams';
    const csrf_token = await this.csrfTokens[service].getToken(
      options?.signal, this.getCsrfTokens
    );
    const query = new URLSearchParams({
      csrf_token,
    });
    return this.sendApiRequest(routeMap.editMps.url({mps_name}), {
      ...options,
      service,
      query,
      method: 'DELETE',
    });
  }

  async validateMultiPeriodStream(data, options) {
    const service = 'streams';
    const csrf_token = await this.csrfTokens[service].getToken(
      options?.signal, this.getCsrfTokens);
    return this.sendApiRequest(routeMap.validateMps.url(), {
      ...options,
      method: 'POST',
      service: 'streams',
      body: JSON.stringify({...data, csrf_token}),
    });
  }

  async sendApiRequest(url: string, options: Partial<ApiRequestOptions>) {
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
        headers.set('Authorization', `Bearer ${this.accessToken.jti}`);
        usedAccessToken = true;
      } else if (service) {
        if (this.csrfTokens[service] === undefined) {
          throw new Error(`Unknown service "${service}"`);
        }
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
    let fetchResult = await fetch(url, {
      cache,
      credentials,
      mode,
      body,
      headers,
      method,
      signal,
    });
    if (signal?.aborted) {
      throw signal.reason;
    }
    if (fetchResult.status === 401 && usedAccessToken && this.refreshToken) {
      const { jti } = this.accessToken;
      await this.getAccessToken(signal);
      if (signal?.aborted) {
        throw signal.reason;
      }
      if (!this.accessToken?.jti || jti === this.accessToken.jti) {
        throw new Error('Failed to refresh access token');
      }
      headers.set('Authorization', `Bearer ${this.accessToken.jti}`);
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
        return fetchResult;
      }
    }
    if (signal?.aborted) {
      throw signal.reason;
    }
    if (fetchResult.status !== 200) {
      return fetchResult;
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

    return data;
  }

  updateCsrfTokens(tokens: Partial<CsrfTokenCollection>) {
    for (const [key, value] of Object.entries(tokens)) {
      if (this.csrfTokens[key] === undefined) {
        this.csrfTokens[key] = new CsrfTokenStore(value);
      } else {
        this.csrfTokens[key].setToken(value);
      }
    }
  }

  async getAccessToken(signal: AbortSignal): Promise<void> {
    if (!this.refreshToken) {
      throw new Error('Cannot request an access token without a refresh token');
    }
    const options = {
      authorization: this.refreshToken.jti,
      rejectOnError: false,
      signal,
    };
    const data: RefreshAccessTokenResponse = await this.sendApiRequest(routeMap.refreshAccessToken.url(), options);
    const { accessToken, csrfTokens, ok, status } = data ?? {};
    if (ok === false && status === 401) {
      document.location.replace(routeMap.login.url());
    }
    if (accessToken) {
      this.accessToken = accessToken;
    }
    if (csrfTokens) {
      this.updateCsrfTokens(csrfTokens);
    }
  }

  getCsrfTokens = async (signal: AbortSignal): Promise<void> => {
    if (!this.accessToken) {
      throw new Error('Cannot request CSRF tokens without an access token');
    }
    const options = {
      authorization: this.accessToken.jti,
      signal,
    };
    const data = await this.sendApiRequest(routeMap.refreshCsrfTokens.url(), options);
    const { csrfTokens } = data ?? {};
    if (csrfTokens) {
      this.updateCsrfTokens(csrfTokens);
    }
  };
}

export function routeFromUrl(url: string) {
  for (const [name, route] of Object.entries(routeMap as RouteMap)) {
    if (route.re.test(url)) {
      return {
        name,
        ...route,
      };
    }
  }
  return undefined;
}

export const EndpointContext = createContext<ApiRequests>(null);
