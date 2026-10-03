import { useEffect, useState, type CSSProperties } from "react";

export type HeroMedia =
  | {
      kind: "image";
      src: string;
      alt: string;
      fit?: "contain" | "cover";
      position?: string;
    }
  | {
      kind: "video";
      src: string;
      poster?: string;
      label?: string;
      fit?: "contain" | "cover";
      position?: string;
    };

type HeroVisualProps = {
  media?: HeroMedia;
};

export function HeroVisual({ media }: HeroVisualProps): React.JSX.Element {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updatePreference = () => setPrefersReducedMotion(mediaQuery.matches);

    updatePreference();
    mediaQuery.addEventListener("change", updatePreference);
    return () => mediaQuery.removeEventListener("change", updatePreference);
  }, []);

  const visualStyle = {
    "--hero-media-fit": media?.fit ?? "contain",
    "--hero-media-position": media?.position ?? "50% 50%",
  } as CSSProperties;

  return (
    <div
      id="architecture"
      className="hero-visual"
      data-has-media={media ? "true" : "false"}
      style={visualStyle}
      aria-hidden={media ? undefined : true}
    >
      <div className="hero-visual__ambient" aria-hidden="true" />

      {media?.kind === "image" && (
        <img className="hero-visual__media" src={media.src} alt={media.alt} />
      )}

      {media?.kind === "video" && (
        <video
          className="hero-visual__media"
          src={media.src}
          poster={media.poster}
          aria-label={media.label}
          aria-hidden={media.label ? undefined : true}
          autoPlay={!prefersReducedMotion}
          loop={!prefersReducedMotion}
          muted
          playsInline
          preload="metadata"
        />
      )}
    </div>
  );
}
