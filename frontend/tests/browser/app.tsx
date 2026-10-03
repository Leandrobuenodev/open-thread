// Loopback test fixture only. Synthetic MSAL context, never a real Entra session.
import React from "react";
import { createRoot } from "react-dom/client";
import { MsalContext } from "@azure/msal-react";
import { InteractionStatus } from "@azure/msal-browser";
import { EntraAuthProvider } from "../../src/auth/AuthProvider";
import App from "../../src/App";
import "../../src/styles.css";
const account = {
  homeAccountId: "local-test-account",
  localAccountId: "local-browser-user",
  tenantId: "local-test-tenant",
  username: "local@example.invalid",
  name: "Local browser test",
};
const instance = {
  getActiveAccount: () => account,
  setActiveAccount: () => {},
  acquireTokenSilent: async () => ({ accessToken: "local-browser-test" }),
};
createRoot(document.getElementById("root")!).render(
  <MsalContext.Provider
    value={
      {
        instance,
        accounts: [account],
        inProgress: InteractionStatus.None,
      } as any
    }
  >
    <EntraAuthProvider>
      <App />
    </EntraAuthProvider>
  </MsalContext.Provider>,
);
