import { useEffect } from "react";
import { IconTrash } from "./MacIcons";

interface GlassModalProps {
  open: boolean;
  tone?: "blue" | "rose";
  title: string;
  description: string;
  cancelLabel: string;
  confirmLabel: string;
  isLoading?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export default function GlassModal({
  open,
  tone = "blue",
  title,
  description,
  cancelLabel,
  confirmLabel,
  isLoading = false,
  onCancel,
  onConfirm,
}: GlassModalProps) {
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        if (!isLoading) {
          onCancel();
        }
      } else if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        if (!isLoading) {
          onConfirm();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [open, isLoading, onCancel, onConfirm]);

  if (!open) return null;

  const badgeToneClasses =
    tone === "rose"
      ? "bg-[#FF453A]/15 border-[#FF453A]/35 text-[#FF6961]"
      : "bg-[#0A84FF]/15 border-[#0A84FF]/35 text-[#0A84FF]";

  const confirmBtnClasses =
    tone === "rose"
      ? "bg-[#FF453A] hover:bg-[#FF554B] text-white"
      : "bg-[#007AFF] hover:bg-[#0071EB] text-white";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="glass-modal-title"
      aria-describedby="glass-modal-desc"
      onClick={() => {
        if (!isLoading) onCancel();
      }}
      className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm flex items-center justify-center p-4 select-none"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-[#262629]/95 backdrop-blur-2xl max-w-[380px] w-full rounded-2xl p-5 border border-white/[0.12] shadow-2xl"
      >
        <div className="flex items-start gap-3.5">
          <div
            className={`w-10 h-10 rounded-xl shrink-0 border flex items-center justify-center ${badgeToneClasses}`}
          >
            <IconTrash className="w-[18px] h-[18px]" />
          </div>

          <div className="min-w-0 flex-1">
            <h3
              id="glass-modal-title"
              className="text-[14px] font-semibold tracking-tight text-[#F2F2F7]"
            >
              {title}
            </h3>
            <p
              id="glass-modal-desc"
              className="text-[12.5px] text-[#AEAEB2] leading-relaxed mt-1"
            >
              {description}
            </p>
          </div>
        </div>

        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            disabled={isLoading}
            onClick={onCancel}
            className="bg-[#3A3A3C] hover:bg-[#48484A] px-4 py-1.5 rounded-[7px] text-[12.5px] font-medium text-[#F2F2F7] disabled:opacity-45 transition-colors cursor-pointer"
          >
            {cancelLabel}
          </button>

          <button
            type="button"
            disabled={isLoading}
            onClick={onConfirm}
            className={`${confirmBtnClasses} px-4 py-1.5 rounded-[7px] text-[12.5px] font-medium disabled:opacity-45 transition-colors shadow-xs cursor-pointer`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
