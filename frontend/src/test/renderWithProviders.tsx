import { render, queries, type RenderOptions, type RenderResult, type Queries } from "@testing-library/preact";
import { memoryLocation } from "wouter-preact/memory-location";
import { Router } from "wouter-preact";

import { AppStateContext, AppStateType, createAppState } from "../appState";
import { bySelectorQueries, BySelectorQueryFunctions } from "./queries";
import { InitialUserState, UserState } from "../types/UserState";
import { computed, signal } from "@preact/signals";
import { vi } from "vitest";
import { UseWhoAmIHook, WhoAmIContext } from "../hooks/useWhoAmI";

const initialUserState: InitialUserState = {
  isAuthenticated: false,
  groups: [],
};

export type RenderWithProvidersProps = RenderOptions & {
  userInfo: InitialUserState;
  whoAmI: UseWhoAmIHook;
  path: string;
  base: string;
  search: string;
  appState: AppStateType;
};

type AllQueryFunctions = Queries & BySelectorQueryFunctions;

export type RenderWithProvidersResult = RenderResult<AllQueryFunctions> & {
  appState: AppStateType;
  whoAmI: UseWhoAmIHook;
};

export function renderWithProviders(
  ui,
  { userInfo, appState, whoAmI, path = "/", ...renderOptions }: Partial<RenderWithProvidersProps> = {}
): RenderWithProvidersResult {
  if (userInfo === undefined) {
    userInfo = structuredClone(initialUserState);
  }
  const userData = signal<InitialUserState>(userInfo);
  const setUser = vi.fn();
  setUser.mockImplementation((ius) => userData.value = structuredClone(ius));
  if (appState === undefined) {
    appState = createAppState();
  }
  if (whoAmI === undefined) {
    const user = computed<UserState>(() => {
      return {
        ...userData.value,
        permissions: {
          admin: userData.value.groups.includes('ADMIN'),
          media: userData.value.groups.includes('MEDIA'),
          user: userData.value.groups.includes('USER'),
        },
      };
    });
    whoAmI = {
      error: signal<string | null>(null),
      checked: signal<boolean>(true),
      user,
      setUser,
    };
  }

  const { hook } = memoryLocation({
    path,
    static: true,
  });

  const Wrapper = ({ children }) => {
    return <AppStateContext.Provider value={appState}>
      <WhoAmIContext.Provider value={whoAmI}>
        <Router hook={hook}>
          {children}
        </Router>
      </WhoAmIContext.Provider></AppStateContext.Provider>;
  };

  return {
    appState,
    whoAmI,
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
