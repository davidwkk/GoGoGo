import { Clock, MapPin, Star } from 'lucide-react';
import type { Activity } from '@/types/trip';

const ActivityImage = ({
  imageUrl,
  name,
  category,
}: {
  imageUrl?: string | null;
  name: string;
  category?: string;
}) => {
  const safeName = encodeURIComponent(name || 'travel');
  const finalImageUrl = imageUrl || `https://picsum.photos/seed/${safeName}/800/600`;

  return (
    // FIX: Removed negative margins. The outer card handles clipping now.
    <div className="w-full h-48 relative bg-slate-100 overflow-hidden">
      <img
        src={finalImageUrl}
        alt={name}
        className="w-full h-full object-cover hover:scale-105 transition-transform duration-300"
      />
      {category && (
        <div className="absolute top-3 left-3 bg-white/90 backdrop-blur-sm px-3 py-1 rounded-full shadow-sm">
          <span className="text-[10px] font-black uppercase tracking-widest text-blue-600">
            {category}
          </span>
        </div>
      )}
    </div>
  );
};

export const AttractionCard = ({
  activity,
  label,
}: {
  activity: Activity | Activity[];
  label: string;
}) => {
  if (!activity || (Array.isArray(activity) && activity.length === 0)) return null;
  const data = Array.isArray(activity) ? activity[0] : activity;

  return (
    <div className="relative pl-8 pb-8 last:pb-0 group">
      {/* Timeline Connector */}
      <div className="absolute left-[11px] top-2 bottom-0 w-px bg-slate-200 group-last:hidden" />
      <div className="absolute left-0 top-1 size-[23px] rounded-full border-4 border-white bg-blue-600 shadow-sm z-10" />

      {/* FIX: Moved p-5 down to the text wrapper, added overflow-hidden to outer card */}
      <div className="bg-white border border-slate-100 rounded-2xl overflow-hidden shadow-sm hover:border-blue-200 transition-all hover:shadow-md flex flex-col">
        <ActivityImage
          imageUrl={data.image_url || data.thumbnail_url}
          name={data.name || 'Activity'}
          category={data.category}
        />

        {/* Text Container (Padding applied here now) */}
        <div className="p-5 flex flex-col">
          <div className="flex justify-between items-start mb-2">
            <span className="text-[10px] font-black uppercase text-blue-500 tracking-tighter">
              {label}
            </span>
            <div className="flex items-center gap-3">
              {data.rating && (
                <div className="flex items-center gap-1 bg-yellow-50 px-2 py-1 rounded-lg">
                  <Star className="size-3 text-yellow-500 fill-yellow-500" />
                  <span className="text-xs font-bold text-yellow-700">{data.rating}</span>
                </div>
              )}
              <div className="flex items-center gap-1 text-slate-400">
                <Clock className="size-3" />
                <span className="text-[10px] font-bold">
                  {data.estimated_duration_minutes || '60'}m
                </span>
              </div>
            </div>
          </div>

          <h4 className="font-bold text-slate-900 leading-tight">{data.name || 'Planned Stop'}</h4>

          <p className="text-[11px] text-slate-500 mt-1 line-clamp-2 leading-relaxed">
            {data.description || 'Enjoy your time exploring this location.'}
          </p>

          <div className="mt-3 flex items-center gap-1.5 text-slate-400">
            <MapPin className="size-3 text-blue-400" />
            <span className="text-[10px] font-medium truncate">
              {data.location || 'Location TBD'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
