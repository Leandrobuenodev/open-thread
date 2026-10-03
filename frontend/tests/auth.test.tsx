// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { InteractionRequiredAuthError } from "@azure/msal-browser";
const mock = vi.hoisted(() => ({
  instance: {
    getActiveAccount: vi.fn(),
    getLogger: vi.fn(),
    setActiveAccount: vi.fn(),
    acquireTokenSilent: vi.fn(),
    acquireTokenPopup: vi.fn(),
    loginPopup: vi.fn(),
    logoutPopup: vi.fn(),
  },
  cancelBridge: vi.fn(),
  inProgress: "none",
  value: null as any,
}));
vi.mock("@azure/msal-browser", async importOriginal => {
  const actual = await importOriginal<typeof import("@azure/msal-browser")>();
  return { ...actual, BrowserUtils: { ...actual.BrowserUtils, cancelPendingBridgeResponse: mock.cancelBridge } };
});
vi.mock("@azure/msal-react", () => ({
  useMsal: () => ({
    accounts: [],
    instance: mock.instance,
    inProgress: mock.inProgress,
  }),
}));
vi.mock("../src/auth/config", () => ({
  entraApiScope: "api://test/chat",
  loginRequest: { scopes: ["api://test/chat"] },
  homeRedirectUri: "http://localhost:5173/",
  msalConfig: { auth: { postLogoutRedirectUri: "http://localhost:5173/redirect.html" } },
}));
import { EntraAuthProvider, useEntraAuth } from "../src/auth/AuthProvider";
function Probe() {
  mock.value = useEntraAuth();
  return null;
}
let root: ReturnType<typeof createRoot>, container: HTMLDivElement;
beforeEach(async () => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  vi.resetAllMocks();
  mock.inProgress = "none";
  mock.instance.getActiveAccount.mockReturnValue({
    homeAccountId: "test-account",
  });
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  await act(async () =>
    root.render(
      <EntraAuthProvider>
        <Probe />
      </EntraAuthProvider>,
    ),
  );
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});
it("requests the configured delegated scope for the active account", async () => {
  mock.instance.acquireTokenSilent.mockResolvedValue({
    accessToken: "test-token",
  });
  expect(await mock.value.getAccessToken()).toBe("test-token");
  expect(mock.instance.acquireTokenSilent).toHaveBeenCalledWith({
    account: { homeAccountId: "test-account" },
    scopes: ["api://test/chat"],
  });
  expect(mock.instance.acquireTokenPopup).not.toHaveBeenCalled();
});
it("uses MSAL interaction when silent renewal requires it", async () => {
  mock.instance.acquireTokenSilent.mockRejectedValue(
    new InteractionRequiredAuthError("interaction_required"),
  );
  mock.instance.acquireTokenPopup.mockResolvedValue({
    accessToken: "renewed-token",
  });
  await act(async () => {
    expect(await mock.value.getAccessToken()).toBe("renewed-token");
  });
  expect(mock.instance.acquireTokenPopup).toHaveBeenCalledOnce();
});
it("rejects empty tokens safely", async () => {
  mock.instance.acquireTokenSilent.mockResolvedValue({ accessToken: " " });
  await expect(mock.value.getAccessToken()).rejects.toThrow(
    "session could not be renewed",
  );
});
it("does not expose MSAL diagnostics on failed renewal", async () => {
  mock.instance.acquireTokenSilent.mockRejectedValue(
    new Error("private account diagnostic"),
  );
  await expect(mock.value.getAccessToken()).rejects.toThrow(
    "session could not be renewed",
  );
  expect(mock.instance.acquireTokenPopup).not.toHaveBeenCalled();
});

it("opens only one login popup until completion and clears activity", async () => {
  let finish!: (value: any) => void;
  mock.instance.loginPopup.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  await act(async () => {
    void mock.value.signIn();
    await mock.value.signIn();
  });
  expect(mock.instance.loginPopup).toHaveBeenCalledOnce();
  expect(mock.value.authAction).toBe("signIn");
  await act(async () => finish({ account: { homeAccountId: "signed-in" } }));
  expect(mock.value.authAction).toBeNull();
  expect(mock.instance.setActiveAccount).toHaveBeenCalledWith({ homeAccountId: "signed-in" });
});
it.each(["startup", "handleRedirect", "acquireToken"])("blocks interaction during %s", async status => {
  mock.inProgress = status;
  await act(async () => root.render(<EntraAuthProvider><Probe /></EntraAuthProvider>));
  await act(async () => { await mock.value.signIn(); });
  expect(mock.instance.loginPopup).not.toHaveBeenCalled();
});
it("recovers from cancellation and allows an immediate retry without an error", async () => {
  mock.instance.loginPopup.mockRejectedValueOnce({ errorCode: "user_cancelled" });
  await act(async () => { await mock.value.signIn().catch(() => {}); });
  expect(mock.value.authError).toBeNull();
  expect(mock.value.authAction).toBeNull();
  mock.instance.loginPopup.mockResolvedValueOnce({ account: { homeAccountId: "retry" } });
  await act(async () => { await mock.value.signIn(); });
  expect(mock.instance.loginPopup).toHaveBeenCalledTimes(2);
});
it("clears actionable errors at the start of a new login", async () => {
  mock.instance.loginPopup.mockRejectedValueOnce({ errorCode: "popup_window_error" });
  await act(async () => { await mock.value.signIn().catch(() => {}); });
  expect(mock.value.authError).toContain("Allow popups");
  let finish!: (value: any) => void;
  mock.instance.loginPopup.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  await act(async () => { void mock.value.signIn(); });
  expect(mock.value.authError).toBeNull();
  await act(async () => finish({ account: { homeAccountId: "retry" } }));
});
it("keeps logout completion in the bridge popup and sends the main window home", async () => {
  mock.instance.logoutPopup.mockResolvedValue(undefined);
  await act(async () => { await mock.value.signOut(); });
  expect(mock.instance.logoutPopup).toHaveBeenCalledWith({
    account: { homeAccountId: "test-account" },
    postLogoutRedirectUri: "http://localhost:5173/redirect.html",
    mainWindowRedirectUri: "http://localhost:5173/",
  });
  expect(mock.value.authAction).toBeNull();
});

it("cancels only the active sign-in bridge through MSAL", async () => {
  const cancel = mock.cancelBridge;
  const logger = { verbose: vi.fn() };
  mock.instance.getLogger = vi.fn().mockReturnValue(logger);
  let fail!: (error: any) => void;
  mock.instance.loginPopup.mockImplementation(() => new Promise((_, reject) => { fail = reject; }));
  await act(async () => { void mock.value.signIn().catch(() => {}); });
  mock.value.cancelSignIn();
  expect(cancel).toHaveBeenCalledWith(logger, "");
  await act(async () => fail({ errorCode: "interaction_in_progress_cancelled" }));
  expect(mock.value.authError).toBeNull();
  expect(mock.value.authAction).toBeNull();
});
