import { useCallback } from "preact/hooks";
import { useSignal } from "@preact/signals";
import { ValidatorSettings } from "../types/ValidatorSettings";

import { ValidatorForm } from "./ValidatorForm";

import { CodecsTable } from "./CodecsTable";
import { Manifest } from "./Manifest";
import { ManifestErrorsTable } from "./ManifestErrorsTable";
import {
  useValidatorWebsocket,
} from "../hooks/useValidatorWebsocket";

import "../styles/validator.less";
import { ProtectedPage } from "../../components/ProtectedPage";
import { LogEntriesCard } from "./LogEntriesCard";
import { wssUrl } from "../utils/wssUrl";
import { ProgressBarWithState } from "./ProgressBarWithState";

export const blankSettings: Readonly<ValidatorSettings> = {
  duration: 30,
  encrypted: false,
  manifest: "",
  media: true,
  prefix: "",
  pretty: false,
  save: false,
  title: "",
  verbose: false,
};
Object.freeze(blankSettings);

export function ValidatorPage() {
  const data = useSignal<ValidatorSettings>({ ...blankSettings });
  const { codecs, errors, log, manifest, progress, state, start, cancel } =
    useValidatorWebsocket(wssUrl(document.location));

    const setValue = useCallback(
    (name: string, value: string | number | boolean) => {
      data.value = {
        ...data.value,
        [name]: value,
      };
    },
    [data]
  );

  return (
    <div id="validator" className="container">
      <ValidatorForm
        data={data}
        state={state}
        setValue={setValue}
        start={start}
        cancel={cancel}
      />
      <ProgressBarWithState progress={progress} state={state} />
      <Manifest manifest={manifest} />
      <ManifestErrorsTable errors={errors} />
      <CodecsTable codecs={codecs} />
      <LogEntriesCard log={log} />
    </div>
  );
}

export default function ProtectedValidatorPage() {
  return (
    <ProtectedPage optional={true}>
      <ValidatorPage />
    </ProtectedPage>
  );
}
