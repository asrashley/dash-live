import { html } from "htm/preact";
import { useCallback, useContext, useRef } from "preact/hooks";
import { useComputed, useSignal, useSignalEffect } from "@preact/signals";

import { TabFormGroup, ModalDialog } from "@dashlive/ui";
import { MultiPeriodModelContext } from "@dashlive/hooks";
import { fieldGroups, defaultShortOptions } from "/libs/options.js";

import { AppStateContext } from "../../appState.js";

const excludeFields = new Set([
  'acodec', 'ad_audio', 'main_audio', 'main_text',
  'player', 'tcodec', 'tlang'
]);

const streamFieldGroups = fieldGroups.map(({fields, name, title}) => ({
  name,
  title,
  fields: fields.filter(({name}) => !excludeFields.has(name)),
}));

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

const formLayout = [3, 4, 5];

export function OptionsDialog({ onClose }) {
  const { dialog } = useContext(AppStateContext);
  const { setFields } = useContext(MultiPeriodModelContext);
  const form = useRef(null);
  const isActive = useComputed(() => dialog.value?.mpsOptions?.name !== undefined);
  const data = useSignal(null);
  const lastUpdated = useSignal(null);

  const onSubmit = useCallback((ev) => {
    ev.preventDefault();
    return false;
  }, []);

  const onSave = useCallback((ev) => {
    ev.preventDefault();
    const options = Object.fromEntries(
      Object.entries(data.value).filter(([key, value]) => defaultShortOptions[key] !== value));
    setFields({ options });
    onClose();
    return false;
  }, [data, setFields, onClose]);

  const setValue = useCallback((name, value) => {
    data.value = {
        ...data.value,
        [name]: value,
    };
  }, [data]);

  useSignalEffect(() => {
    if (!dialog.value?.mpsOptions) {
      return;
    }
    const { lastModified, options } = dialog.value.mpsOptions;
    if (lastUpdated.value === lastModified && data.value !== null) {
      return;
    }
    data.value = {
        ...defaultShortOptions,
        ...options,
    };
    lastUpdated.value = lastModified;
    // optionsToFormData(shortNamesToOptions(dialog.value.mpsOptions.options)),
  });

  if (!isActive.value) {
    return null;
  }

  const footer = html`<${Footer} onClose=${onClose} onSave=${onSave} />`;

  return html`
    <${ModalDialog} onClose=${onClose} title="Stream Options" size='xl' footer=${footer}>
      <form name="mpsOptions" ref=${form} onSubmit=${onSubmit}>
        <${TabFormGroup} groups=${streamFieldGroups} layout=${formLayout} data=${data} setValue=${setValue} mode="shortName" />
      </form>
    </${ModalDialog}>`;
}
