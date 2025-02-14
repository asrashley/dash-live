import { DecoratedStream } from "../../types/DecoratedStream";
import { ValidatorSettings } from "../types/ValidatorSettings";
import { ValidatorSettingsErrors } from "../types/ValidatorSettingsErrors";

export function checkValidatorSettings(settings: ValidatorSettings, allStreams: DecoratedStream[]): ValidatorSettingsErrors {
  const errs: ValidatorSettingsErrors = {};
  if (!settings.manifest) {
    errs.manifest = 'manifest URL is required';
  }
  if (settings.duration < 1 || settings.duration > 3600) {
    errs.duration = "duration must be >= 1 second and <= 3600 seconds";
  }
  if (settings.save) {
    if (!settings.prefix) {
      errs.prefix = 'a directory name is required';
    } else if (allStreams.some(({directory}) => directory === settings.prefix)) {
      errs.prefix = `a stream already exists with name ${settings.prefix}`;
    }
    if (!settings.title) {
      errs.title = 'a title is required';
    }
  }
  return errs;
}
