import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import fetchMock from "@fetch-mock/vitest";
import { act, fireEvent } from "@testing-library/preact";
import userEvent from "@testing-library/user-event";
import log from "loglevel";
import { setImmediate } from "timers";

import { ApiRequests, EndpointContext } from "../../endpoints";
import { FakeEndpoint } from "../../test/FakeEndpoint";
import { MockDashServer, mediaUser } from "../../test/MockServer";
import { renderWithProviders } from "../../test/renderWithProviders";
import { EditStreamForm, EditStreamFormProps } from "./EditStreamForm";
import { AllStreamsContext, useAllStreams } from "../../hooks/useAllStreams";
import {
  MultiPeriodModelContext,
  useMultiPeriodStream,
} from "../../hooks/useMultiPeriodStream";
import { InitialUserState } from "../../types/UserState";
import { routeMap, uiRouteMap } from "@dashlive/routemap";
import { useLocation } from "wouter-preact";

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
        <EditStreamForm name={name} newStream={newStream} />
      </MultiPeriodModelContext.Provider>
    </AllStreamsContext.Provider>
  );
}

describe("EditStreamForm component", () => {
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
    const { pk, username, email, groups } = user;
    userInfo = {
      pk,
      username,
      email,
      groups,
    };
    api = new ApiRequests({needsRefreshToken, hasUserInfo});
    api.setRefreshToken(user.refreshToken);
    api.setAccessToken(user.accessToken);
  });

  afterEach(() => {
    endpoint.shutdown();
    vi.clearAllMocks();
    fetchMock.mockReset();
  });

  test("matches snapshot for an existing stream", async () => {
    expect(userInfo).toBeDefined();
    const { asFragment, findByText, findAllByText, whoAmI } =
      renderWithProviders(<Wrapper newStream={false} name={mps_name} />, {
        userInfo,
      });
    expect(whoAmI.user.value).toEqual({
      ...userInfo,
      isAuthenticated: true,
      permissions: {
        admin: false,
        user: true,
        media: true,
      },
    });
    await findByText('"europe-ntp"');
    await findAllByText("Tears of Steel");
    expect(asFragment()).toMatchSnapshot();
  });

  test.each<[string, boolean]>([
    ["edit a stream", false],
    ["create a new stream", true],
  ])("edit %s and save changes", async (_title:string, newStream: boolean) => {
    expect(userInfo).toBeDefined();
    const user = userEvent.setup();
    const { getByText, findAllByText, findBySelector, getBySelector } = renderWithProviders(
      <Wrapper newStream={newStream} name={newStream ? ".add" : mps_name} />,
      { userInfo }
    );
    if (!newStream) {
      await findAllByText("Tears of Steel");
    }
    const editProm = endpoint.addResponsePromise(
      newStream ? "put" : "post",
      newStream ? routeMap.addMps.url() : routeMap.editMps.url({ mps_name })
    );
    const nameElt = getBySelector('input[name="name"]') as HTMLInputElement;
    const titleElt = getBySelector('input[name="title"]') as HTMLInputElement;
    await user.clear(nameElt);
    await user.type(nameElt, "newname{enter}");
    await user.clear(titleElt);
    await user.type(titleElt, "title for this stream{enter}");
    if (newStream) {
      const addBtn = getByText("Add a Period") as HTMLButtonElement;
      await user.click(addBtn);
      const streamSel = await findBySelector('.period-stream select') as HTMLSelectElement;
      await user.selectOptions(streamSel, "Tears of Steel");
    }
    const btn = getByText(newStream ? "Save new stream" : "Save Changes") as HTMLButtonElement;
    expect(btn.disabled).toEqual(false);
    await user.click(btn);
    await expect(editProm).resolves.toEqual(
      expect.objectContaining({ status: 200 })
    );
    // allow the await for saveChanges() to have been processed
    await new Promise<void>(setImmediate);
    if (newStream) {
      expect(setLocation).toHaveBeenCalledWith(uiRouteMap.listMps.url());
    } else {
      expect(setLocation).not.toHaveBeenCalled();
    }
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
    act(() => {
      appState.dialog.value = {
        backdrop: true,
        confirmDelete: {
          confirmed: true,
          name: mps_name,
        },
      };
    });
    await expect(delProm).resolves.toEqual(
      expect.objectContaining({ status: 204 })
    );
    // allow the await for deleteStream() to have been processed
    await new Promise<void>(setImmediate);
    expect(setLocation).toHaveBeenCalledTimes(1);
    expect(setLocation).toHaveBeenCalledWith(uiRouteMap.listMps.url());
  });
});
