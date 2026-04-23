// TravelSettingsBar — Collapsible bar above InputBar with travel preferences

import { Settings, ChevronDown } from 'lucide-react';

import { TripPlanningPreferenceFields } from '@/components/chat/TripPlanningPreferenceFields';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useChatStore } from '@/store';

const LLM_MODELS: { value: string; label: string }[] = [
  { value: 'gemini-3.1-flash-lite-preview', label: '3.1 Flash Lite (Fast)' },
  { value: 'gemini-3-flash-preview', label: '3 Flash (Smart)' },
  { value: 'gemini-2.5-flash-lite', label: '2.5 Flash Lite (Backup)' },
  { value: 'gemini-2.5-flash', label: '2.5 Flash (Backup)' },
];

export function TravelSettingsBar() {
  const llm_model = useChatStore(s => s.llm_model);
  const setLlmModel = useChatStore(s => s.setLlmModel);

  return (
    <details className="border-t bg-muted/20">
      <summary className="flex cursor-pointer select-none items-center gap-2 px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground list-none">
        <Settings className="size-4" />
        <span>Preferences</span>
        <ChevronDown className="size-4 ml-auto transition-transform duration-200 details[open]_:rotate-180" />
      </summary>

      <div className="flex flex-wrap items-center gap-4 px-4 pb-4">
        <TripPlanningPreferenceFields />

        {/* LLM Model */}
        <div className="space-y-1">
          <Label htmlFor="llm_model" className="text-xs">
            Model
          </Label>
          <Select
            value={llm_model}
            onValueChange={val => {
              setLlmModel(val);
            }}
          >
            <SelectTrigger id="llm_model" className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {LLM_MODELS.map(m => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </details>
  );
}
