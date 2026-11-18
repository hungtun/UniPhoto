import { ScanProgressState } from "../api/PhotoApi";
import LanguageSwitcher from "../components/LanguageSwitcher";
import {
  IconClose,
  IconDuplicates,
  IconSparkles,
} from "../components/MacIcons";
import { useI18n } from "../i18n/I18nContext";
import { localizeBackendFileStatus } from "../i18n/translations";

interface ScanningPageProps {
  folderPath: string;
  scanPhaseText: string;
  progress: ScanProgressState;
  isCancelling: boolean;
  onCancelScan: () => void;
}

export default function ScanningPage({
  folderPath,
  scanPhaseText,
  progress,
  isCancelling,
  onCancelScan,
}: ScanningPageProps) {
  const { lang, t, isWindows } = useI18n();
  const localizedFile = localizeBackendFileStatus(progress.current_file, lang);

  const badgeLabel =
    progress.phase === "cancelled" || isCancelling
      ? t.scanning.badgeCancelled
      : progress.phase === "aesthetic_scoring"
      ? t.scanning.badgeAesthetics
      : progress.phase === "clustering"
      ? t.scanning.badgeClustering
      : t.scanning.badgeScanning;

  const isAiPhase =
    progress.phase === "clustering" || progress.phase === "aesthetic_scoring";

  return (
    <div className="h-screen w-screen bg-[#161618] text-[#F2F2F7] flex flex-col justify-between overflow-hidden select-none">
      {/* Top Titlebar with macOS Traffic-Light Safe Zone / Windows Standard Padding */}
      <header
        data-tauri-drag-region
        className={`h-[46px] ${
          isWindows ? "pl-5" : "pl-[80px]"
        } pr-4 bg-[#1C1C1E] border-b border-white/[0.07] flex items-center justify-between shrink-0`}
      >
        <div
          data-tauri-drag-region
          className="flex items-center gap-2 pointer-events-none"
        >
          <img
            src="/logo.png"
            alt="UniPhoto"
            className="w-5 h-5 rounded-[5px] object-contain"
            onError={(e) => {
              e.currentTarget.style.display = "none";
            }}
          />
          <span className="text-[13px] font-semibold tracking-tight text-[#F2F2F7]">
            UniPhoto
          </span>
        </div>

        <LanguageSwitcher compact />
      </header>

      <main className="flex-1 flex items-center justify-center px-6 py-4">
        <div className="bg-[#1E1E20] border border-white/[0.08] rounded-2xl p-7 max-w-md w-full shadow-xl">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-[#0A84FF]/14 border border-[#0A84FF]/25 text-[#0A84FF] flex items-center justify-center shrink-0">
                {isAiPhase ? (
                  <IconSparkles className="w-5 h-5" />
                ) : (
                  <IconDuplicates className="w-5 h-5" />
                )}
              </div>
              <div className="min-w-0">
                <span className="text-[11px] uppercase tracking-wider font-semibold text-[#0A84FF] block">
                  {badgeLabel}
                </span>
                <span className="text-[12px] text-[#8E8E93] tabular-nums block mt-0.5">
                  {progress.total > 0
                    ? t.scanning.photoProgress(progress.current, progress.total)
                    : t.scanning.checkingFolder}
                </span>
              </div>
            </div>

            <span className="text-2xl font-semibold tracking-tight text-[#F2F2F7] tabular-nums shrink-0">
              {progress.percent}%
            </span>
          </div>

          <h2 className="text-[13.5px] font-medium text-[#F2F2F7] mt-5 leading-snug">
            {scanPhaseText}
          </h2>

          <div className="mt-3 w-full h-[6px] rounded-full bg-white/[0.10] overflow-hidden">
            <div
              className="h-full bg-[#007AFF] transition-all duration-200 rounded-full"
              style={{ width: `${Math.min(100, Math.max(0, progress.percent))}%` }}
            />
          </div>

          <p className="text-[11.5px] text-[#8E8E93] truncate mt-2.5">
            {localizedFile
              ? t.scanning.checkingFile(localizedFile)
              : folderPath
              ? t.scanning.folderPrefix(folderPath)
              : t.scanning.checkingFolder}
          </p>

          {progress.phase === "scanning" && progress.total > 0 && (
            <div className="mt-4 bg-[#252528] border border-white/[0.06] rounded-lg px-3.5 py-2 flex items-center justify-between text-[12px]">
              <span className="text-[#AEAEB2]">
                {t.scanning.keptPhotos}{" "}
                <b className="text-[#30D158] font-semibold tabular-nums">
                  {progress.new_added}
                </b>
              </span>
              <span className="text-white/[0.14]">|</span>
              <span className="text-[#AEAEB2]">
                {t.scanning.duplicatePhotos}{" "}
                <b className="text-[#0A84FF] font-semibold tabular-nums">
                  {progress.exact_duplicates}
                </b>
              </span>
            </div>
          )}

          <button
            type="button"
            onClick={onCancelScan}
            disabled={isCancelling}
            className="mt-5 w-full bg-[#2C2C2E] hover:bg-[#3A3A3C] border border-white/[0.08] text-[#F2F2F7] py-2 px-4 rounded-[8px] text-[12.5px] font-medium inline-flex items-center justify-center gap-1.5 disabled:opacity-50 disabled:pointer-events-none transition-colors cursor-pointer"
          >
            <IconClose className="w-[13px] h-[13px] text-[#AEAEB2]" />
            <span>
              {isCancelling
                ? t.scanning.btnCancelling
                : t.scanning.btnCancelScan}
            </span>
          </button>
        </div>
      </main>

      <div className="h-4 shrink-0" />
    </div>
  );
}
