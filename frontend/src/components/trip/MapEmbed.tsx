// frontend/src/components/trip/MapEmbed.tsx
export function MapEmbed({ url }: { url: string | null }) {
  if (!url) return null;

  return (
    <section className="w-full h-full">
      <iframe
        title="Trip Map"
        width="100%"
        height="100%"
        style={{ border: 0 }}
        src={url}
        allowFullScreen
      ></iframe>
    </section>
  );
}
