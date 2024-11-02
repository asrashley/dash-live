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
  { preloadedState, state, path = "/", ...renderOptions } = {}
) {
  if (preloadedState === undefined) {
    preloadedState = { ...initialUserState };
  }
  if (state === undefined) {
    state = createAppState(preloadedState);
  }
  const { hook } = memoryLocation({
    path,
    static: true,
  });

  const Wrapper = ({ state, children }) => {
    return html`<${AppStateContext.Provider} value=${state}
      ><${Router} hook=${hook}>${children}<//><//
    >`;
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
