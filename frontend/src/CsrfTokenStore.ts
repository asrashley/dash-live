interface PendingRequest {
  resolve: (token: string) => void;
  reject: (reason: any) => void;
}

export class CsrfTokenStore {
  private pending: PendingRequest[];

  constructor(private token: string | null) {
    this.pending = [];
  }

  setToken(token: string): void {
    if (this.pending.length) {
      const {resolve} = this.pending.shift();
      resolve(token)
    } else {
      this.token = token;
    }
  }

  async getToken(signal: AbortSignal, refreshFn?: (sig?: AbortSignal) => Promise<void>): Promise<string> {
    if (!this.token && refreshFn) {
      await refreshFn(signal);
    }
    const { token } = this;
    if (token) {
      this.token = null;
      return token;
    }

    const {promise, resolve, reject} = Promise.withResolvers<string>();
    const abortListener = () => {
      reject(signal.reason);
    };
    signal?.addEventListener('abort', abortListener);
    this.pending.push({resolve, reject});
    promise.finally(() => {
      this.pending = this.pending.filter(p => p.resolve !== resolve);
      signal?.removeEventListener('abort', abortListener);
    });
    return await promise;
  }
}
