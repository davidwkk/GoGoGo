// frontend/src/components/trip/MapEmbed.tsx
export function MapEmbed({ url }: { url: string | null }) {
  if (!url) return null;

  return (
    <section>
      <div className="w-full h-[300px] rounded-[2.5rem] overflow-hidden border border-slate-100 shadow-inner">
        <iframe
          title="Trip Map"
          width="100%"
          height="100%"
          style={{ border: 0 }}
          src={url}
          allowFullScreen
        ></iframe>
      </div>
    </section>
  );
}
