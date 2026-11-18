import { useEffect } from "react";
import { IconCheckCircle, IconClose, IconWarning } from "./MacIcons";

export type ToastTone = "success" | "warning" | "error";

interface GlassToastProps {
  toastId: number | null;
  tone: ToastTone;
  message: string;
  dismissLabel: string;
  durationMs?: number;
  onClose: () => void;
}

export default function GlassToast({
  toastId,
  tone,
  message,
  dismissLabel,
  durationMs = 4000,
  onClose,
}: GlassToastProps) {
  useEffect(() => {
    if (toastId === null || !message) return;
    const timer = window.setTimeout(() => {
      onClose();
    }, durationMs);
    return () => window.clearTimeout(timer);
  }, [toastId, message, durationMs, onClose]);

  if (toastId === null || !message) return null;

  const iconToneCls =
    tone === "success"
      ? "text-[#30D158]"
      : tone === "warning"
      ? "text-[#FFD60A]"
      : "text-[#FF453A]";

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-5 right-5 z-50 max-w-md bg-[#262629]/95 backdrop-blur-xl border border-white/[0.12] rounded-xl px-3.5 py-2.5 flex items-center gap-2.5 shadow-xl select-none"
    >
      <span className={`shrink-0 flex items-center justify-center ${iconToneCls}`}>
        {tone === "success" ? (
          <IconCheckCircle className="w-[17px] h-[17px]" />
        ) : (
          <IconWarning className="w-[17px] h-[17px]" />
        )}
      </span>

      <p className="text-[12.5px] font-medium text-[#F2F2F7] leading-snug flex-1 min-w-0">
        {message}
      </p>

      <button
        type="button"
        onClick={onClose}
        aria-label={dismissLabel}
        title={dismissLabel}
        className="w-6 h-6 rounded-md flex items-center justify-center text-[#8E8E93] hover:text-white hover:bg-white/[0.08] transition-colors cursor-pointer shrink-0"
      >
        <IconClose className="w-[13px] h-[13px]" />
      </button>
    </div>
  );
}
