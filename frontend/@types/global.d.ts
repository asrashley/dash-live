declare const _GIT_HASH_: string;
declare module "*.module.css";
declare module "*.less" {
    const content: Record<string, string>;
    export default content;
}
