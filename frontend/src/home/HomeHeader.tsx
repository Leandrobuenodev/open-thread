import { InterfaceIcon } from "../components/InterfaceIcon";

type HomeHeaderProps = {
  isBusy: boolean;
  onSignIn: () => Promise<void>;
};

export function HomeHeader({
  isBusy,
  onSignIn,
}: HomeHeaderProps): React.JSX.Element {
  return (
    <header className="home-header home-container">
      <a className="home-brand" href="#home" aria-label="Open Thread home">
        <span className="home-brand__symbol" aria-hidden="true">
          <InterfaceIcon name="brand" />
        </span>
        <span className="home-brand__name">Open Thread</span>
        <span className="home-brand__index">/01</span>
      </a>
      <nav aria-label="Main navigation">
        <a href="#experience">Experience</a>
        <a href="#system">The system</a>
        <a href="#engineering">Engineering</a>
      </nav>
      <button
        id="start"
        className="home-header__entry"
        onClick={() => void onSignIn()}
        disabled={isBusy}
        type="button"
      >
        <svg
          className="home-microsoft-mark"
          viewBox="0 0 16 16"
          aria-hidden="true"
        >
          <path fill="#f25022" d="M0 0h7.5v7.5H0z" />
          <path fill="#7fba00" d="M8.5 0H16v7.5H8.5z" />
          <path fill="#00a4ef" d="M0 8.5h7.5V16H0z" />
          <path fill="#ffb900" d="M8.5 8.5H16V16H8.5z" />
        </svg>
        <span>{isBusy ? "Signing in…" : "Sign in with Microsoft"}</span>
      </button>
    </header>
  );
}
