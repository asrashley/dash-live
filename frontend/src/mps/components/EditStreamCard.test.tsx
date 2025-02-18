import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import fetchMock from "@fetch-mock/vitest";
import { fireEvent } from "@testing-library/preact";
import { useLocation } from "wouter-preact";
import log from "loglevel";
import { setImmediate } from "timers";

import { routeMap, uiRouteMap } from "@dashlive/routemap";

import { ApiRequests, EndpointContext } from "../../endpoints";
import { FakeEndpoint } from "../../test/FakeEndpoint";
import { MockDashServer, mediaUser } from "../../test/MockServer";
import { renderWithProviders } from "../../test/renderWithProviders";
import { EditStreamFormProps } from "./EditStreamForm";
import { AllStreamsContext, useAllStreams } from "../../hooks/useAllStreams";
import {
  MultiPeriodModelContext,
  useMultiPeriodStream,
} from "../../hooks/useMultiPeriodStream";
import { InitialUserState } from "../../user/types/InitialUserState";
import { EditStreamCard } from "./EditStreamCard";

vi.mock("wouter-preact", async (importOriginal) => {
  return {
    ...(await importOriginal()),
    useLocation: vi.fn(),
  };
});

function AllStreams({ name, newStream }: EditStreamFormProps) {
  const allStreams = useAllStreams();
  const modelContext = useMultiPeriodStream({ name, newStream });

  return (
    <AllStreamsContext.Provider value={allStreams}>
      <MultiPeriodModelContext.Provider value={modelContext}>
        <EditStreamCard name={name} newStream={newStream} />
      </MultiPeriodModelContext.Provider>
    </AllStreamsContext.Provider>
  );
}

describe("EditStreamCard", () => {
  const needsRefreshToken = vi.fn();
  const hasUserInfo = vi.fn();
  const setLocation = vi.fn();
  const useLocationMock = vi.mocked(useLocation);
  const mps_name = "demo";
  let endpoint: FakeEndpoint;
  let server: MockDashServer;
  let api: ApiRequests;
  let userInfo: InitialUserState;

  const Wrapper = ({ name, newStream }: EditStreamFormProps) => {
    return (
      <EndpointContext.Provider value={api}>
        <AllStreams name={name} newStream={newStream} />
      </EndpointContext.Provider>
    );
  };

  beforeEach(() => {
    log.setLevel("error");
    useLocationMock.mockReturnValue([
      routeMap.editMps.url({ mps_name }),
      setLocation,
    ]);
    endpoint = new FakeEndpoint(document.location.origin);
    server = new MockDashServer({
      endpoint,
    });
    const user = server.login(mediaUser.email, mediaUser.password);
    expect(user).not.toBeNull();
    expect(user.groups).toEqual(mediaUser.groups);
    const { pk, username, email, groups, lastLogin, mustChange } = user;
    userInfo = {
      pk,
      username,
      email,
      groups,
      lastLogin,
      mustChange,
    };
    api = new ApiRequests({ needsRefreshToken, hasUserInfo });
    api.setRefreshToken(user.refreshToken);
    api.setAccessToken(user.accessToken);
  });

  afterEach(() => {
    endpoint.shutdown();
    vi.clearAllMocks();
    fetchMock.mockReset();
  });

  test("can delete a stream", async () => {
    expect(userInfo).toBeDefined();
    const { findByText, appState, whoAmI } = renderWithProviders(
      <Wrapper newStream={false} name={mps_name} />,
      { userInfo }
    );
    expect(whoAmI.user.value).toEqual({
      ...userInfo,
      isAuthenticated: true,
      permissions: {
        admin: false,
        user: true,
        media: true,
      },
    });
    expect(useLocationMock).toHaveBeenCalled();
    await findByText('"europe-ntp"');
    expect(appState.dialog.value).toBeNull();
    const btn = (await findByText("Delete Stream")) as HTMLButtonElement;
    fireEvent.click(btn);
    expect(appState.dialog.value).toEqual({
      backdrop: true,
      confirmDelete: {
        confirmed: false,
        name: mps_name,
      },
    });
    const delProm = endpoint.addResponsePromise(
      "delete",
      routeMap.editMps.url({ mps_name })
    );
    const delBtn = (await findByText("Yes, I'm sure")) as HTMLButtonElement;
    fireEvent.click(delBtn);
    await expect(delProm).resolves.toEqual(
      expect.objectContaining({ status: 204 })
    );
    // allow the await for deleteStream() to have been processed
    await new Promise<void>(setImmediate);
    expect(setLocation).toHaveBeenCalledTimes(1);
    expect(setLocation).toHaveBeenCalledWith(uiRouteMap.listMps.url());
  });
});
