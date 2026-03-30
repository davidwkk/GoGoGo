import { Clock, MapPin } from 'lucide-react';
import type { Activity } from '@/types/trip';

const ActivityImage = ({ imageUrl, name }: { imageUrl?: string | null; name: string }) => {
  if (!imageUrl) return null;
  return (
    <div className="w-full h-32 mb-4 -mx-5 -mt-5 rounded-t-2xl overflow-hidden bg-slate-100">
      <img
        src={imageUrl}
        alt={name}
        className="w-full h-full object-cover hover:scale-105 transition-transform duration-300"
      />
    </div>
  );
};

export const ActivityCard = ({
  activity,
  label,
}: {
  activity: Activity | Activity[];
  label: string;
}) => {
  // If activity is null or an empty array/object, don't show the card
  if (!activity || (Array.isArray(activity) && activity.length === 0)) return null;

  // Handle if David sends an array of one item instead of an object
  const data = Array.isArray(activity) ? activity[0] : activity;

  return (
    <div className="relative pl-8 pb-8 last:pb-0 group">
      {/* Timeline Connector */}
      <div className="absolute left-[11px] top-2 bottom-0 w-px bg-slate-200 group-last:hidden" />
      <div className="absolute left-0 top-1 size-[23px] rounded-full border-4 border-white bg-blue-600 shadow-sm z-10" />

      <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm hover:border-blue-200 transition-all hover:shadow-md">
        <ActivityImage
          imageUrl={data.image_url || data.thumbnail_url}
          name={data.name || 'Activity'}
        />

        <div className="flex justify-between items-start mb-2">
          <span className="text-[10px] font-black uppercase text-blue-500 tracking-tighter">
            {label}
          </span>
          <div className="flex items-center gap-1 text-slate-400">
            <Clock className="size-3" />
            <span className="text-[10px] font-bold">
              {data.estimated_duration_minutes || '60'}m
            </span>
          </div>
        </div>

        {/* Accessing keys name, description, location from David's JSON */}
        <h4 className="font-bold text-slate-900 leading-tight">{data.name || 'Planned Stop'}</h4>

        <p className="text-[11px] text-slate-500 mt-1 line-clamp-2 leading-relaxed">
          {data.description || 'Enjoy your time exploring this location.'}
        </p>

        <div className="mt-3 flex items-center gap-1.5 text-slate-400">
          <MapPin className="size-3 text-blue-400" />
          <span className="text-[10px] font-medium truncate">
            {data.location || 'Tokyo, Japan'}
          </span>
        </div>
      </div>
    </div>
  );
};
