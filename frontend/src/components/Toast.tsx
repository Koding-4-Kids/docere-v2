// frontend/src/components/Toast.tsx
import { useEffect } from 'react';

export type ToastType = 'success' | 'error' | 'info';

interface ToastProps {
  type: ToastType;
  message: string;
  onClose: () => void;
}

export function Toast({ type, message, onClose }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  // Inside Toast.tsx
  const icons = {
    success: '✓', // Or use an SVG/Icon library component
    error: '!',
    info: 'i',
  };

  const styles = {
    success: 'bg-green-900/80 border-green-700 text-green-100',
    error: 'bg-red-900/80 border-red-700 text-red-100',
    info: 'bg-blue-900/80 border-blue-700 text-blue-100',
  };

  return (
    <div className={`${styles[type]} px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 min-w-[300px] animate-fade-in border`}>
      
      {/* Icon Container */}
      <div className="flex-shrink-0 w-6 h-6 flex items-center justify-center font-bold">
        {type === 'success' && '✓'}
        {type === 'error' && '!'}
        {type === 'info' && 'i'}
      </div>

      {/* Message */}
      <span className="text-sm font-medium flex-grow">{message}</span>

      {/* Close Button */}
      <button onClick={onClose} className="opacity-70 hover:opacity-100 flex-shrink-0">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}