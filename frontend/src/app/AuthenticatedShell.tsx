// LEGACY / HISTORICAL / NOT CURRENT ARCHITECTURE: disconnected release-intelligence experiment.
import type { PropsWithChildren } from "react";

export type AppSection = "overview" | "releases" | "incidents" | "investigator" | "integrations";

type AuthenticatedShellProps = PropsWithChildren<{
  activeSection: AppSection;
  authError: string | null;
  onNavigate: (section: AppSection) => void;
  onSignOut: () => Promise<void>;
  userName: string;
}>;

const sections: Array<{ id: AppSection; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "releases", label: "Releases" },
  { id: "incidents", label: "Incidents" },
  { id: "investigator", label: "AI Investigator" },
];

export function AuthenticatedShell({
  activeSection,
  authError,
  children,
  onNavigate,
  onSignOut,
  userName,
}: AuthenticatedShellProps): React.JSX.Element {
  return (
    <div className="product-shell">
      <header className="product-header">
        <button className="product-brand" onClick={() => onNavigate("overview")} type="button">
          <span className="product-brand__mark" aria-hidden="true">
            <span />
            <span />
          </span>
          <span>Open Thread</span>
        </button>

        <nav className="product-nav" aria-label="Authenticated navigation">
          {sections.map((section) => (
            <button
              className={`product-nav__link${activeSection === section.id ? " product-nav__link--active" : ""}`}
              aria-current={activeSection === section.id ? "page" : undefined}
              key={section.id}
              onClick={() => onNavigate(section.id)}
              type="button"
            >
              {section.label}
            </button>
          ))}
        </nav>

        <div className="product-header__account">
          <button
            className={`product-header__settings${activeSection === "integrations" ? " product-header__settings--active" : ""}`}
            onClick={() => onNavigate("integrations")}
            type="button"
          >
            Settings
          </button>
          <span className="product-header__user" title={userName}>
            {userName}
          </span>
          <button className="product-header__signout" onClick={() => void onSignOut().catch(() => undefined)} type="button">
            Sign out
          </button>
        </div>
      </header>

      {authError && (
        <p className="product-shell__auth-error" role="alert">
          {authError}
        </p>
      )}

      <main className="product-main">{children}</main>
    </div>
  );
}
