import "./liquid-glass-nav.css";

export type LiquidGlassNavItem = {
  label: string;
  href: string;
};

type LiquidGlassNavProps = {
  items: LiquidGlassNavItem[];
  activeHref?: string;
};

export function LiquidGlassNav({
  items,
  activeHref,
}: LiquidGlassNavProps): React.JSX.Element {
  return (
    <nav className="liquid-glass-nav" aria-label="Primary navigation">
      <svg className="liquid-glass-nav__filters" aria-hidden="true">
        <defs>
          <filter
            id="liquid-glass-nav-refraction"
            x="-10%"
            y="-20%"
            width="120%"
            height="140%"
          >
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.018 0.07"
              numOctaves="2"
              seed="7"
              result="noise"
            />
            <feDisplacementMap
              in="SourceGraphic"
              in2="noise"
              scale="3"
              xChannelSelector="R"
              yChannelSelector="G"
            />
          </filter>
        </defs>
      </svg>

      <span className="liquid-glass-nav__refraction" aria-hidden="true" />
      <span className="liquid-glass-nav__highlight" aria-hidden="true" />
      <span className="liquid-glass-nav__links">
        {items.map((item) => {
          const isActive = item.href === activeHref;
          return (
            <a
              className={`liquid-glass-nav__link${isActive ? " liquid-glass-nav__link--active" : ""}`}
              href={item.href}
              aria-current={isActive ? "page" : undefined}
              key={item.href}
            >
              <span className="liquid-glass-nav__label">{item.label}</span>
            </a>
          );
        })}
      </span>
    </nav>
  );
}
