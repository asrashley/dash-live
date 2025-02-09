import { useCallback } from "preact/hooks";
import { useComputed, useSignal } from "@preact/signals";
import { ProgressBar } from "./ProgressBar";
import { ValidatorSettings } from "../types/ValidatorSettings";

import { ValidatorForm } from "./ValidatorForm";

import { CodecsTable } from "./CodecsTable";
import { Manifest } from "./Manifest";
import { ManifestErrorsTable } from "./ManifestErrorsTable";
import { useValidatorWebsocket, ValidatorState } from "../hooks/useValidatorWebsocket";

import "../styles/validator.less";
import { ProtectedPage } from "../../components/ProtectedPage";
import { LogEntriesCard } from "./LogEntriesCard";

declare const _SERVER_PORT_: number | null;

function wssUrl(): string {
  const { protocol, hostname, port } = new URL(document.location.href);
  return `${protocol}//${hostname}:${_SERVER_PORT_ ?? port}/`;
}

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

const stateClassMap = {
  [ValidatorState.IDLE]: "text-bg-secondary",
  [ValidatorState.ACTIVE]: "bg-success-subtle text-dark",
  [ValidatorState.CANCELLING]: "bg-danger",
  [ValidatorState.CANCELLED]: "bg-warning-subtle text-dark",
  [ValidatorState.DONE]: "bg-success",
};

export default function ValidatorPage() {
  const data = useSignal<ValidatorSettings>({ ...blankSettings });
  const { codecs, errors, log, manifest, progress, state, start, cancel } =
    useValidatorWebsocket(wssUrl());
  const stateClass = useComputed<string>(() => `position-absolute top-0 start-50 translate-middle badge rounded-pill ${stateClassMap[state.value]}`);

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
    <ProtectedPage optional={true}>
      <div id="validator" className="container">
        <ValidatorForm
          data={data}
          state={state}
          setValue={setValue}
          start={start}
          cancel={cancel}
        />
        <div className="position-relative">
          <div className="card progress">
            <ProgressBar progress={progress} />
          </div>
          <div className={stateClass}>
            {state}
          </div>
        </div>
        <Manifest manifest={manifest} />
        <ManifestErrorsTable errors={errors} />
        <CodecsTable codecs={codecs} />
        <LogEntriesCard log={log} />
      </div>
    </ProtectedPage>
  );
}
