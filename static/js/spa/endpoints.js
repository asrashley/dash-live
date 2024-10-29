import { createContext } from 'preact';
import { routeMap } from '/libs/routemap.js';

class CsrfTokenStore {
  constructor(token) {
    this.token = token;
    this.pending = [];
  }

  setToken(token) {
    if (this.pending.length) {
      const {resolve} = this.pending.shift();
      resolve(token)
    } else {
      this.token = token;
    }
  }

  async getToken(signal) {
    const { token } = this;
    if (token) {
      this.token = null;
      return token;
    }
    const {promise, resolve, reject} = Promise.withResolvers();
    if (signal) {
      signal.addEventListener('abort', () => {
        reject(signal.reason);
      });
    }
    this.pending.push({resolve, reject});
    promise.finally(() => {
      this.pending = this.pending.filter(p => p.resolve !== resolve);
    });
    return await promise;
  }
}

export class ApiRequests {
  constructor({csrfTokens, accessToken, refreshToken}) {
    this.csrfTokens = {
      files: new CsrfTokenStore(csrfTokens?.files),
      kids: new CsrfTokenStore(csrfTokens?.kids),
      streams: new CsrfTokenStore(csrfTokens?.streams),
      upload: new CsrfTokenStore(csrfTokens?.upload),
    }
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
  }

  getAllStreams({ withDetails = false, ...options} = {}) {
    const query = withDetails ? new URLSearchParams({details:1}) : undefined;
    return this.sendApiRequest(routeMap.listStreams.url(), {
      service: 'streams',
      query,
      ...options,
    });
  }

  getAllMultiPeriodStreams(options) {
    return this.sendApiRequest(routeMap.listMps.url(), {
      service: 'streams',
      ...options,
    });
  }

  getMultiPeriodStream(mps_name, options) {
    return this.sendApiRequest(routeMap.editMps.url({mps_name}), {
      service: 'streams',
      ...options,
    });
  }

  addMultiPeriodStream(data, options) {
    return this.sendApiRequest(routeMap.addMps.url(), {
      ...options,
      service: 'streams',
      body: JSON.stringify(data),
      method: 'PUT',
    });
  }

  modifyMultiPeriodStream(mps_name, data, options) {
    return this.sendApiRequest(routeMap.editMps.url({mps_name}), {
      ...options,
      service: 'streams',
      body: JSON.stringify(data),
      method: 'POST',
    });
  }

  async sendApiRequest(url, options) {
    const { authorization, body, service, signal, method='GET' } = options;
    let { query } = options;
    if (this.csrfTokens[service] === undefined) {
      throw new Error(`Unknown service "${service}"`);
    }
    const headers = {
      "Content-Type": "application/json",
    }
    if (authorization !== undefined) {
      headers.Authorization = `Bearer ${authorization}`;
    } else {
      if (!this.accessToken && this.refreshToken) {
        await this.getAccessToken(signal);
      }
      if (this.accessToken) {
        headers.Authorization = `Bearer ${this.accessToken.jti}`;
      } else {
        const token = await this.csrfTokens[service].getToken();
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
    const fetchResult = await fetch(url, {
      cache: 'no-cache',
      credentials: 'same-origin',
      mode: 'same-origin',
      body,
      headers,
      method,
      signal,
    });
    if (!fetchResult.ok) {
      throw new Error(`Failed to fetch ${ url }: ${ fetchResult.status }`);
    }
    if (signal && signal.aborted) {
      throw signal.reason;
    }
    const data = await fetchResult.json();
    if (typeof(data?.csrfTokens) === "object") {
      this.updateCsrfTokens(data.csrfTokens);
    } else if(typeof(data?.csrf_tokens) === "object") {
      this.updateCsrfTokens(data.csrf_tokens);
    } else if (typeof(data?.csrf_token) === "string") {
      this.updateCsrfTokens({[service]: data.csrf_token});
    }

    return data;
  }

  updateCsrfTokens(tokens) {
    for (const [key, value] of Object.entries(tokens)) {
      if (this.csrfTokens[key] === undefined) {
        this.csrfTokens[key] = new CsrfTokenStore(value);
      } else {
        this.csrfTokens[key].setToken(value);
      }
    }
  }

  async getAccessToken(signal) {
    if (this.refreshToken === undefined) {
      throw new Error('Cannot request an access token without a refresh token');
    }
    const options = {
      authorization: this.refreshToken.jti,
      signal,
    };
    const data = await this.sendApiRequest(routeMap.getAccessToken, {}, options);
    const { accessToken } = data ?? {};
    if (accessToken) {
      this.accessToken = accessToken;
    }
  }
};

export function routeFromUrl(url) {
  for (const [name, route] of Object.entries(routeMap)) {
    if (route.re.test(url)) {
      return {
        name,
        ...route,
      };
    }
  }
  return undefined;
}

export const EndpointContext = createContext(null);
