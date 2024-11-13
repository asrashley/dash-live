import { html } from "htm/preact";
import { useCallback, useContext, useRef } from "preact/hooks";
import { useComputed } from "@preact/signals";

import { AccordionFormGroup, ModalDialog } from "@dashlive/ui";
import { MultiPeriodModelContext } from "@dashlive/hooks";
import { fieldGroups } from "/libs/options.js";

import { AppStateContext } from "../../appState.js";
import {
  shortNamesToOptions,
  optionsToShortNames,
  nonDefaultOptions,
  formToOptions,
  optionsToFormData,
} from "../../dashOptions.js";

function Footer({ onClose, onSave }) {
  return html`<div role="group">
    <button type="button" class="btn btn-success me-3" onClick=${onSave}>
      Save Changes
    </button>
    <button type="button" class="btn btn-warning" onClick=${onClose}>
      Discard Changes
    </button>
  </div>`;
}

export function OptionsDialog({ onClose }) {
  const { dialog } = useContext(AppStateContext);
  const { setFields } = useContext(MultiPeriodModelContext);
  const form = useRef(null);
  const isActive = useComputed(() => dialog.value?.mpsOptions?.name !== undefined);
  const mpsOptions = useComputed(() =>
    isActive ? optionsToFormData(shortNamesToOptions(dialog.value.mpsOptions.options)) : null);

  const onSubmit = useCallback((ev) => {
    ev.preventDefault();
    return false;
  }, []);

  const onSave = useCallback(() => {
    const options = optionsToShortNames(
      nonDefaultOptions(formToOptions(form.current))
    );
    setFields({ options });
    onClose();
    return false;
  }, [onClose, form, setFields]);

  if (!isActive.value) {
    return null;
  }

  const footer = html`<${Footer} onClose=${onClose} onSave=${onSave} />`;

  return html`
    <${ModalDialog} onClose=${onClose} title="Stream Options" size='xl' footer=${footer}>
      <form name="mpsOptions" ref=${form} onSubmit=${onSubmit}>
        <${AccordionFormGroup} groups=${fieldGroups} data=${mpsOptions} />
      </form>
    </${ModalDialog}>`;
}
