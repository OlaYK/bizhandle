import type { PropsWithChildren } from "react";
import { X } from "lucide-react";
import { Button } from "./button";

interface ModalProps extends PropsWithChildren {
  open: boolean;
  title: string;
  onClose: () => void;
}

export function Modal({ open, title, onClose, children }: ModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end bg-surface-900/40 p-3 md:items-center md:justify-center">
      <div className="w-full max-w-lg animate-fade-up rounded-2xl bg-white p-4 shadow-soft dark:border dark:border-surface-700 dark:bg-surface-900 md:p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-heading text-xl font-bold text-surface-800 dark:text-surface-100">{title}</h3>
          <Button type="button" variant="ghost" size="sm" onClick={onClose} className="h-8 px-2">
            <X className="h-4 w-4" />
          </Button>
        </div>
        {children}
      </div>
      <button
        type="button"
        className="fixed inset-0 -z-10 h-full w-full"
        onClick={onClose}
        aria-label="Close modal"
      />
    </div>
  );
}
