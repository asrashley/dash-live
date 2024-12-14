import { html } from "htm/preact";
import { render, queries } from "@testing-library/preact";
import { memoryLocation } from "wouter-preact/memory-location";
import { Router } from "wouter-preact";

import { AppStateContext, createAppState } from "../spa/appState.js";
import { bySelectorQueries } from "./queries";

const initialUserState = {
  isAuthenticated: false,
  groups: [],
};

export function renderWithProviders(
  ui,
  { userInfo, state, path = "/", ...renderOptions } = {}
) {
  if (userInfo === undefined) {
    userInfo = { ...initialUserState };
  }
  if (state === undefined) {
    state = createAppState(userInfo);
  }

  const { hook } = memoryLocation({
    path,
    static: true,
  });

  const Wrapper = ({ children }) => {
    return html`<${AppStateContext.Provider} value=${state}
      ><${Router} hook=${hook}>${children}<//><//>`;
  };

  return {
    state,
    ...render(ui, {
      wrapper: Wrapper,
      queries: {
        ...queries,
        ...bySelectorQueries,
      },
      ...renderOptions,
    }),
  };
}
