function withResolvers<T>(): PromiseWithResolvers<T> {
    let resolve: (value: T) => void;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let reject: (reason?: any) => void;
    const promise = new Promise<T>((res, rej) => {
        resolve = res;
        reject = rej;
    });
    return { resolve, reject, promise };
}

export function installAllPolyfills() {
    if (Promise.withResolvers === undefined) {
        Object.defineProperty(Promise, 'withResolvers', {
            configurable: false,
            value: withResolvers,
            writable: false,
        });
    }
}
