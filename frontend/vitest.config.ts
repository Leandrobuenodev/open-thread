import viteConfig from "./vite.config";

// Synthetic public settings for isolated tests; never loaded by production builds.
export default {
  ...viteConfig,
  test: {
    env: {
      VITE_ENTRA_CLIENT_ID: "00000000-0000-0000-0000-000000000001",
      VITE_ENTRA_AUTHORITY:
        "https://login.microsoftonline.com/00000000-0000-0000-0000-000000000002/v2.0",
      VITE_ENTRA_API_SCOPE: "api://unit-test/access_as_user",
      VITE_ENTRA_REDIRECT_URI: "http://localhost:5173/redirect.html",
    },
  },
};
