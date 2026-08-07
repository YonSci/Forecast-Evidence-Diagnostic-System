import { useLightbox } from "./Lightbox";

export function MapFigure({ src, caption }: { src: string; caption: string }) {
  const openLightbox = useLightbox();
  const title = caption.split(" — ")[0] ?? caption;

  return (
    <figure className="map-figure" onClick={() => openLightbox({ src, caption })}>
      <img src={src} alt={caption} loading="lazy" />
      <figcaption>
        <b>{title}</b>
        {caption}
      </figcaption>
    </figure>
  );
}
