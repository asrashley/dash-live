declare module "preact-lazy" {
    import { ComponentType } from "preact";

    type LazyImport = () => Promise<{ default: ComponentType<any> }>;

    function lazy(
        importFn: LazyImport,
        fallback?: ComponentType<any>,
        loaded?: ComponentType<any>,
    ): ComponentType<any>;

    export default lazy;
}
