import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle } from 'lucide-react';

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  destructive?: boolean;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  destructive = false,
}: ConfirmDialogProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-200">
          <div className="flex flex-col h-full">
            <div className="flex items-start gap-3">
              {destructive && (
                <div className="mt-0.5 shrink-0 rounded-full bg-red-50 p-2">
                  <AlertTriangle className="size-4 text-red-600" />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <Dialog.Title className="text-base font-semibold text-slate-900 leading-snug">
                  {title}
                </Dialog.Title>
                <Dialog.Description className="mt-1.5 text-sm text-slate-500 leading-relaxed">
                  {description}
                </Dialog.Description>
              </div>
            </div>
            <div className="mt-10 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className="h-9 rounded-xl border border-slate-200 bg-white px-4 text-sm font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors"
              >
                {cancelLabel}
              </button>
              <button
                type="button"
                onClick={() => {
                  onConfirm();
                  onOpenChange(false);
                }}
                className={`h-9 rounded-xl px-4 text-sm font-medium transition-colors ${
                  destructive
                    ? 'bg-red-600 text-white hover:bg-red-700 shadow-sm'
                    : 'bg-slate-900 text-white hover:bg-slate-800 shadow-sm'
                }`}
              >
                {confirmLabel}
              </button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
