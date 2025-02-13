import { type ComponentChild } from "preact";

import {
  renderWithProviders,
  RenderWithProvidersProps,
  RenderWithProvidersResult,
} from "../../test/renderWithProviders";

export type ValidatorFormHtmlElements = {
    manifestElt: HTMLInputElement;
    destinationElt: HTMLInputElement;
    durationElt: HTMLInputElement;
    encryptedElt: HTMLInputElement;
    saveElt: HTMLInputElement;
    titleElt: HTMLInputElement;
    startBtn: HTMLButtonElement;
    cancelBtn: HTMLButtonElement;
  };

  export type ValidatorFormRenderResult = RenderWithProvidersResult &
    ValidatorFormHtmlElements;

  export function renderWithFormAccess(
    ui: ComponentChild,
    renderProps: Partial<RenderWithProvidersProps> = {}
  ): ValidatorFormRenderResult {
    const renderRes = renderWithProviders(ui, renderProps);
    const { getByText, getByLabelText } = renderRes;

    return {
      ...renderRes,
      manifestElt: getByLabelText("Manifest to check:") as HTMLInputElement,
      durationElt: getByLabelText("Maximum duration:") as HTMLInputElement,
      encryptedElt: getByLabelText("Stream is encrypted?") as HTMLInputElement,
      destinationElt: getByLabelText(
        "Destination directory:"
      ) as HTMLInputElement,
      titleElt: getByLabelText("Stream title:") as HTMLInputElement,
      saveElt: getByLabelText("Add stream to this server?") as HTMLInputElement,
      startBtn: getByText("Validate DASH stream") as HTMLButtonElement,
      cancelBtn: getByText("Cancel") as HTMLButtonElement,
    } as unknown as ValidatorFormRenderResult;
  }

