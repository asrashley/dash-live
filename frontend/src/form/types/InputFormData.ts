export type InputFormData = {
    [name: string]: InputFormData | string | number | boolean | null | Date | [number, string][] | Array<string | number> | Array<unknown> | undefined;
};