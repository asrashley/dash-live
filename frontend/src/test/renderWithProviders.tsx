import { vi } from "vitest";
import { type ComponentChild } from "preact";
import { computed, signal } from "@preact/signals";
import {
  render,
  queries,
  type RenderOptions,
  type RenderResult,
  type Queries,
} from "@testing-library/preact";
import { memoryLocation } from "wouter-preact/memory-location";
import { Router } from "wouter-preact";

import { AppStateContext, AppStateType, createAppState } from "../appState";
import { bySelectorQueries, BySelectorQueryFunctions } from "./queries";
import { InitialUserState } from "../user/types/InitialUserState";
import { UserState } from "../user/types/UserState";
import { UseWhoAmIHook, WhoAmIContext } from "../user/hooks/useWhoAmI";
import { FlattenedUserState } from "../user/types/FlattenedUserState";
import { flattenUserState } from "../user/utils/flattenUserState";

const initialUserState: InitialUserState = {
  mustChange: false,
  lastLogin: null,
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
  ui: ComponentChild,
  {
    userInfo,
    appState,
    whoAmI,
    path = "/",
    ...renderOptions
  }: Partial<RenderWithProvidersProps> = {}
): RenderWithProvidersResult {
  if (!userInfo) {
    userInfo = structuredClone(initialUserState);
  }
  const userData = signal<InitialUserState>(userInfo);
  const setUser = vi.fn();
  setUser.mockImplementation(
    (ius: InitialUserState | null) =>
      (userData.value = ius
        ? structuredClone(ius)
        : structuredClone(initialUserState))
  );
  if (appState === undefined) {
    appState = createAppState();
  }
  if (whoAmI === undefined) {
    const user = computed<UserState>(() => {
      return {
        ...userData.value,
        isAuthenticated: userData.value.pk !== undefined,
        permissions: {
          admin: userData.value.groups.includes("ADMIN"),
          media: userData.value.groups.includes("MEDIA"),
          user: userData.value.groups.includes("USER"),
        },
      };
    });
    const flattened = computed<FlattenedUserState>(() => flattenUserState(user.value));
    whoAmI = {
      user,
      flattened,
      setUser,
    };
  }

  const { hook } = memoryLocation({
    path,
    static: true,
  });

  const Wrapper = ({ children }) => {
    return (
      <AppStateContext.Provider value={appState}>
        <WhoAmIContext.Provider value={whoAmI}>
          <Router hook={hook}>{children}</Router>
        </WhoAmIContext.Provider>
      </AppStateContext.Provider>
    );
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
