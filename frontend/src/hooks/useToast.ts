import { createContext, useContext } from 'react';
import { type ToastType } from '../components/Toast';

interface ToastContextType {
  addToast: (type: ToastType, message: string) => void;
}

export const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used within ToastProvider');
  return context;
};