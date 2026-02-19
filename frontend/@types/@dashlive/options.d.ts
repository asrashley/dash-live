import { InputFormGroup } from "../../src/form/types/InputFormGroup";
import { OptionsContainerType } from "./dash-options";

type OptionMap = {
  [field: string]: boolean | string | number | null;
};

export const defaultFullOptions: OptionsContainerType;

export const defaultShortOptions: OptionMap;

export const defaultCgiOptions: OptionMap;

export const drmSystems: string[];

export const groupNames: string[];

export const fieldGroups: InputFormGroup[];
