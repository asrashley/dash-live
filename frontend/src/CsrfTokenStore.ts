interface PendingRequest {
  resolve: (token: string) => void;
  reject: (reason: never) => void;
}

export class CsrfTokenStore {
  private pending: PendingRequest[];

  constructor(private token: string | null) {
    this.pending = [];
  }

  setToken(token: string): void {
    if (this.pending.length) {
      const pending = this.pending.shift();
      pending?.resolve(token);
    } else {
      this.token = token;
    }
  }

  async getToken(signal: AbortSignal | undefined, refreshFn?: (sig?: AbortSignal) => Promise<void>): Promise<string> {
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
      if (signal) {
        const { reason } = signal;
        if (reason instanceof Error) {
          reject(reason);
        } else {
          reject(new Error(`${reason ?? 'aborted'}`));
        }
      }
    };
    try{
      signal?.addEventListener('abort', abortListener);
      this.pending.push({resolve, reject});
      return await promise;
    } finally {
      this.pending = this.pending.filter(p => p.resolve !== resolve);
      signal?.removeEventListener('abort', abortListener);
    }
  }
}
