import type { CSSProperties } from "react";

type BackgroundPlateProps = {
  src?: string;
  position?: string;
};

export function BackgroundPlate({
  src,
  position = "center center",
}: BackgroundPlateProps): React.JSX.Element {
  const plateStyle = {
    "--background-plate-position": position,
  } as CSSProperties;

  return (
    <div
      className={`home-background-plate${src ? "" : " home-background-plate--fallback"}`}
      style={plateStyle}
      aria-hidden="true"
    >
      {src && <img src={src} alt="" />}
    </div>
  );
}
