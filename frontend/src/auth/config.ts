import type { Configuration, PopupRequest } from "@azure/msal-browser";

function requiredEnvironmentValue(name: string): string {
  const value = import.meta.env[name];
  if (!value?.trim()) {
    throw new Error(`${name} is not configured.`);
  }
  return value.trim();
}

export const entraApiScope = requiredEnvironmentValue("VITE_ENTRA_API_SCOPE");

export const homeRedirectUri = new URL("/", window.location.origin).href;

export const msalConfig: Configuration = {
  auth: {
    clientId: requiredEnvironmentValue("VITE_ENTRA_CLIENT_ID"),
    authority: requiredEnvironmentValue("VITE_ENTRA_AUTHORITY"),
    redirectUri: requiredEnvironmentValue("VITE_ENTRA_REDIRECT_URI"),
    postLogoutRedirectUri: requiredEnvironmentValue("VITE_ENTRA_REDIRECT_URI"),
  },
  cache: {
    cacheLocation: "sessionStorage",
  },
};

export const loginRequest: PopupRequest = {
  scopes: [entraApiScope],
};
