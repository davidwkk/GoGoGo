import { X } from 'lucide-react';
import { useEffect } from 'react';
import { createPortal } from 'react-dom';

export function ImageLightbox({
  imageUrl,
  altText,
  onClose,
}: {
  imageUrl: string;
  altText: string;
  onClose: () => void;
}) {
  // Close on escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Prevent scrolling on the body when lightbox is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);

  if (typeof document === 'undefined') return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      onClick={onClose}
    >
      <button
        onClick={onClose}
        className="absolute top-6 right-6 text-white/70 hover:text-white bg-black/20 hover:bg-black/40 rounded-full p-2 transition-all"
        aria-label="Close image"
      >
        <X className="size-8" />
      </button>

      <img
        src={imageUrl}
        alt={altText}
        className="max-w-full max-h-[90vh] object-contain rounded-lg shadow-2xl scale-100 animate-in zoom-in-95 duration-200"
        onClick={e => e.stopPropagation()} // Prevent closing when clicking the image itself
      />
    </div>,
    document.body
  );
}
