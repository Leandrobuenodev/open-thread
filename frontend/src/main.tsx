import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { PublicClientApplication } from "@azure/msal-browser";
import { MsalProvider } from "@azure/msal-react";
import "./styles.css";

const root = createRoot(document.getElementById("root")!);

async function bootstrap() {
  // Load configuration-dependent modules inside the startup error boundary.
  const [
    { default: App },
    { AuthGate },
    { EntraAuthProvider },
    { msalConfig },
  ] = await Promise.all([
    import("./App"),
    import("./auth/AuthGate"),
    import("./auth/AuthProvider"),
    import("./auth/config"),
  ]);
  const msalInstance = new PublicClientApplication(msalConfig);
  await msalInstance.initialize();
  // Finish pending response/cache cleanup before interactive controls mount.
  await msalInstance.handleRedirectPromise().catch(() => {
    // MSAL has cleaned up the failed response; keep the landing retryable.
    if (import.meta.env.DEV) console.warn("Microsoft redirect processing failed; sign-in can be retried.");
  });
  root.render(
    <StrictMode>
      <MsalProvider instance={msalInstance}>
        <EntraAuthProvider>
          <AuthGate>
            <App />
          </AuthGate>
        </EntraAuthProvider>
      </MsalProvider>
    </StrictMode>,
  );
}

void bootstrap().catch(() => {
  root.render(
    <main className="auth-shell">
      <h1>Unable to start Open Thread.</h1>
      <p role="alert">Check the application configuration and reload.</p>
    </main>,
  );
});
