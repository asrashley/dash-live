import { render, queries, RenderOptions, RenderResult, Queries } from "@testing-library/preact";
import { memoryLocation } from "wouter-preact/memory-location";
import { Router } from "wouter-preact";

import { AppStateContext, AppStateType, createAppState } from "../appState";
import { bySelectorQueries, BySelectorQueryFunctions } from "./queries";
import { InitialUserState } from "../types/UserState";

const initialUserState: InitialUserState = {
  isAuthenticated: false,
  groups: [],
};

export type RenderWithProvidersProps = RenderOptions & {
  userInfo: InitialUserState;
  path: string;
  base: string;
  search: string;
  state: AppStateType;
};

type AllQueryFunctions = Queries & BySelectorQueryFunctions;

export type RenderWithProvidersResult = RenderResult<AllQueryFunctions> & {
  state: AppStateType;
};

export function renderWithProviders(
  ui,
  { userInfo, state, path = "/", ...renderOptions }: Partial<RenderWithProvidersProps> = {}
): RenderWithProvidersResult {
  if (userInfo === undefined) {
    userInfo = structuredClone(initialUserState);
  }
  if (state === undefined) {
    state = createAppState(userInfo);
  }

  const { hook } = memoryLocation({
    path,
    static: true,
  });

  const Wrapper = ({ children }) => {
    return <AppStateContext.Provider value={state}
      ><Router hook={hook}>{children}</Router></AppStateContext.Provider>;
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
  } as unknown as RenderWithProvidersResult;
}
