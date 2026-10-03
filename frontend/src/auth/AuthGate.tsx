import { InteractionStatus } from "@azure/msal-browser";
import { Fragment, type PropsWithChildren } from "react";

import { HomePage } from "../home/HomePage";
import { useEntraAuth } from "./AuthProvider";

export function AuthGate({ children }: PropsWithChildren): React.JSX.Element {
  const { account, authError, authAction, inProgress, signIn, cancelSignIn } = useEntraAuth();

  async function handleSignIn() {
    try {
      await signIn();
    } catch {
      // Only the provider's safe, actionable message is shown.
    }
  }

  const preparing = inProgress === InteractionStatus.Startup ||
    inProgress === InteractionStatus.HandleRedirect;
  if (!account || preparing) {
    const signingIn = authAction === "signIn" ||
      inProgress === InteractionStatus.AcquireToken;
    return (
      <HomePage
        authError={authError}
        isBusy={Boolean(authAction) || inProgress !== InteractionStatus.None}
        authStatus={signingIn ? "Signing in with Microsoft…" :
          preparing ? "Preparing Microsoft sign-in…" : null}
        onSignIn={handleSignIn}
        onCancelSignIn={authAction === "signIn" ? cancelSignIn : undefined}
      />
    );
  }

  // Keep authenticated children mounted while tokens are renewed.
  return <Fragment key={account.homeAccountId}>{children}</Fragment>;
}
