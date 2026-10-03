import {
  BrowserUtils,
  InteractionRequiredAuthError,
  InteractionStatus,
  type AccountInfo,
} from "@azure/msal-browser";
import { useMsal } from "@azure/msal-react";
import {
  type PropsWithChildren,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { entraApiScope, homeRedirectUri, loginRequest, msalConfig } from "./config";

type EntraAuthContextValue = {
  account: AccountInfo | null;
  authError: string | null;
  authAction: "signIn" | "signOut" | "renew" | null;
  inProgress: InteractionStatus;
  getAccessToken: () => Promise<string>;
  signIn: () => Promise<void>;
  cancelSignIn: () => void;
  signOut: () => Promise<void>;
};

function authErrorCode(error: unknown): string {
  if (error && typeof error === "object" && "errorCode" in error &&
    typeof error.errorCode === "string" && /^[a-z_]+$/.test(error.errorCode)) {
    return error.errorCode;
  }
  return "unknown_error";
}

function logAuthFailure(operation: string, code: string) {
  if (import.meta.env.DEV && code !== "user_cancelled" && code !== "interaction_in_progress_cancelled") {
    // Never log the error object: it may contain account/server details.
    console.warn(`Microsoft ${operation} failed (${code}).`);
  }
}

const EntraAuthContext = createContext<EntraAuthContextValue | null>(null);

export function EntraAuthProvider({
  children,
}: PropsWithChildren): React.JSX.Element {
  const { accounts, instance, inProgress } = useMsal();
  const [authError, setAuthError] = useState<string | null>(null);
  const [authAction, setAuthAction] = useState<EntraAuthContextValue["authAction"]>(null);
  // A ref closes the gap before MSAL events/React updates disable the buttons.
  const interacting = useRef(false);
  const account = instance.getActiveAccount() ?? accounts[0] ?? null;

  useEffect(() => {
    if (
      inProgress === InteractionStatus.None &&
      account &&
      instance.getActiveAccount()?.homeAccountId !== account.homeAccountId
    ) {
      instance.setActiveAccount(account);
    }
  }, [account, inProgress, instance]);

  const signIn = useCallback(async () => {
    if (interacting.current || inProgress !== InteractionStatus.None) return;
    interacting.current = true;
    setAuthAction("signIn");
    setAuthError(null);
    try {
      const result = await instance.loginPopup(loginRequest);
      if (result.account) instance.setActiveAccount(result.account);
      setAuthError(null);
    } catch (error) {
      const code = authErrorCode(error);
      if (code !== "user_cancelled" && code !== "interaction_in_progress_cancelled") {
        setAuthError(code === "popup_window_error" || code === "empty_window_error"
          ? "Allow popups for Open Thread, then try signing in again."
          : "We couldn’t sign you in. Please try again.");
      }
      logAuthFailure("sign-in", code);
      throw error;
    } finally {
      interacting.current = false;
      setAuthAction(null);
    }
  }, [inProgress, instance]);

  const cancelSignIn = useCallback(() => {
    if (authAction !== "signIn") return;
    // MSAL v5 deliberately cannot observe popup closure after a COOP split.
    // Cancel its bridge monitor and let MSAL perform normal interaction cleanup.
    BrowserUtils.cancelPendingBridgeResponse(instance.getLogger(), "");
  }, [authAction, instance]);

  const signOut = useCallback(async () => {
    if (interacting.current || inProgress !== InteractionStatus.None) return;
    interacting.current = true;
    setAuthAction("signOut");
    setAuthError(null);
    try {
      await instance.logoutPopup({
        account: account ?? undefined,
        // The popup returns to the v5 bridge; the main window returns home.
        postLogoutRedirectUri: msalConfig.auth.postLogoutRedirectUri ?? undefined,
        mainWindowRedirectUri: homeRedirectUri,
      });
    } catch (error) {
      if (authErrorCode(error) !== "user_cancelled") {
        setAuthError("We couldn’t complete sign-out. Please try again.");
      }
      logAuthFailure("sign-out", authErrorCode(error));
      throw error;
    } finally {
      interacting.current = false;
      setAuthAction(null);
    }
  }, [account, inProgress, instance]);

  const getAccessToken = useCallback(async () => {
    if (!account) throw new Error("Sign in before sending a message.");

    try {
      let result;
      try {
        result = await instance.acquireTokenSilent({
          account,
          scopes: [entraApiScope],
        });
      } catch (error) {
        if (!(error instanceof InteractionRequiredAuthError)) throw error;
        if (interacting.current || inProgress !== InteractionStatus.None) {
          throw new Error("Authentication interaction already active.");
        }
        interacting.current = true;
        setAuthAction("renew");
        try {
          result = await instance.acquireTokenPopup({
            account,
            scopes: [entraApiScope],
          });
        } finally {
          interacting.current = false;
          setAuthAction(null);
        }
      }
      if (!result.accessToken.trim()) throw new Error("Empty access token.");
      return result.accessToken;
    } catch {
      throw new Error(
        "Your session could not be renewed. Sign out and sign in again.",
      );
    }
  }, [account, inProgress, instance]);

  const value = useMemo(
    () => ({
      account,
      authError,
      authAction,
      inProgress,
      getAccessToken,
      signIn,
      cancelSignIn,
      signOut,
    }),
    [account, authError, authAction, getAccessToken, inProgress, signIn, cancelSignIn, signOut],
  );

  return (
    <EntraAuthContext.Provider value={value}>
      {children}
    </EntraAuthContext.Provider>
  );
}

export function useEntraAuth(): EntraAuthContextValue {
  const context = useContext(EntraAuthContext);
  if (!context) {
    throw new Error("useEntraAuth must be used inside EntraAuthProvider.");
  }
  return context;
}
