export function importLibrary<T>(jsUrl: string): Promise<T> {
    return import(/* webpackIgnore: true */ jsUrl) as Promise<T>;
}