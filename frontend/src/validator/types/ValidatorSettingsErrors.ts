import { ValidatorSettings } from "./ValidatorSettings";


export type ValidatorSettingsErrors = Partial<Record<keyof ValidatorSettings, string>>;
