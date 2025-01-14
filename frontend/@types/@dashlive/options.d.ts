import { InputFormGroup } from "../../src/types/InputFormGroup";

type OptionMap = {
  [field: string]: boolean | string | number | null;
};

type OptionMapWithChildren = {
  [field: string]: boolean | string | number | null | OptionMap;
};

export const defaultFullOptions: OptionMapWithChildren;


export const defaultShortOptions: OptionMap;

export const defaultCgiOptions: OptionMap;

export const drmSystems: string[];

export const fieldGroups: InputFormGroup[];