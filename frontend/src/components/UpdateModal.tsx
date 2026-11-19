import { useCallback, useEffect } from "react";
import { useI18n } from "../i18n/I18nContext";
import { UpdateInfo, openExternalReleaseUrl } from "../utils/updater";
import { IconArrowDownCircle } from "./MacIcons";

interface UpdateModalProps {
  open: boolean;
  info: UpdateInfo | null;
  onClose: () => void;
}

export default function UpdateModal({ open, info, onClose }: UpdateModalProps) {
  const { t, formatBytes, isWindows } = useI18n();

  const handleDownload = useCallback(() => {
    if (!info) return;
    void openExternalReleaseUrl(info.downloadUrl);
    onClose();
  }, [info, onClose]);

  useEffect(() => {
    if (!open || !info) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      } else if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        handleDownload();
      }
    };

    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [open, info, onClose, handleDownload]);

  if (!open || !info) return null;

  const trimmedNotes = info.releaseNotes.trim();
  const hasAssetSize =
    info.assetSizeBytes !== null &&
    Number.isFinite(info.assetSizeBytes) &&
    info.assetSizeBytes > 0;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="update-modal-title"
      onClick={onClose}
      className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm flex items-center justify-center p-4 select-none"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-[#262629]/95 backdrop-blur-2xl max-w-[430px] w-full rounded-2xl p-5 border border-white/[0.12] shadow-2xl"
      >
        <div className="flex items-start gap-3.5">
          <div className="w-10 h-10 rounded-xl shrink-0 border bg-[#0A84FF]/15 border-[#0A84FF]/35 text-[#0A84FF] flex items-center justify-center">
            <IconArrowDownCircle className="w-[19px] h-[19px]" />
          </div>

          <div className="min-w-0 flex-1">
            <h3
              id="update-modal-title"
              className="text-[14.5px] font-semibold tracking-tight text-[#F2F2F7]"
            >
              {t.update.modalTitle(info.latestVersion)}
            </h3>

            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-[#0A84FF]/15 border border-[#0A84FF]/30 text-[11.5px] font-medium text-[#64D2FF] tabular-nums">
                <span>
                  {t.update.versionTransition(
                    info.currentVersion,
                    info.latestVersion
                  )}
                </span>
                {hasAssetSize && info.assetSizeBytes !== null && (
                  <>
                    <span className="text-[#64D2FF]/50" aria-hidden="true">
                      •
                    </span>
                    <span>{formatBytes(info.assetSizeBytes)}</span>
                  </>
                )}
              </span>

              {info.assetName && (
                <span
                  title={info.assetName}
                  className="text-[11px] text-[#8E8E93] truncate max-w-[170px]"
                >
                  {info.assetName}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="mt-4">
          <p className="text-[11px] font-medium text-[#8E8E93] mb-1.5">
            {t.update.releaseNotesLabel}
          </p>
          <div className="max-h-[140px] overflow-y-auto bg-[#1C1C1E] border border-white/[0.07] rounded-xl px-3.5 py-2.5 text-[12px] text-[#D1D1D6] whitespace-pre-line leading-relaxed select-text">
            {trimmedNotes || t.update.defaultNotes}
          </div>
        </div>

        <div className="mt-3.5 space-y-1.5">
          <p className="text-[11.5px] text-[#8E8E93] leading-relaxed">
            {t.update.safeUpgradeHint}
          </p>

          {!isWindows && (
            <p className="text-[11.5px] text-[#8E8E93] leading-relaxed">
              <span>{t.update.macGatekeeperHint} </span>
              <code className="select-text font-mono text-[10.5px] text-[#D1D1D6] bg-[#1C1C1E] border border-white/[0.08] rounded px-1.5 py-0.5">
                xattr -cr /Applications/UniPhoto.app
              </code>
            </p>
          )}
        </div>

        <div className="mt-5 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => {
              void openExternalReleaseUrl(info.releasePageUrl);
            }}
            className="text-[12px] font-medium text-[#8E8E93] hover:text-[#64D2FF] transition-colors cursor-pointer truncate"
          >
            {t.update.btnViewReleasePage}
          </button>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="bg-[#3A3A3C] hover:bg-[#48484A] px-3.5 py-1.5 rounded-[7px] text-[12.5px] font-medium text-[#F2F2F7] transition-colors cursor-pointer"
            >
              {t.update.btnLater}
            </button>

            <button
              type="button"
              onClick={handleDownload}
              className="bg-[#007AFF] hover:bg-[#0071EB] text-white px-4 py-1.5 rounded-[7px] text-[12.5px] font-medium transition-colors shadow-xs cursor-pointer inline-flex items-center gap-1.5"
            >
              <IconArrowDownCircle className="w-[14px] h-[14px]" />
              <span>{t.update.btnDownload}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
