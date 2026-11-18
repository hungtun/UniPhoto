import CustomCheckbox from "../components/CustomCheckbox";
import LanguageSwitcher from "../components/LanguageSwitcher";
import { IconFolder, IconPhotoStack } from "../components/MacIcons";
import { useI18n } from "../i18n/I18nContext";

interface HomePageProps {
  folderPath: string;
  isDraggingFolder: boolean;
  onDragStateChange: (dragging: boolean) => void;
  onDropPath?: (path: string) => void;
  runAiClusterToo: boolean;
  setRunAiClusterToo: (val: boolean) => void;
  clearOldDataBeforeScan: boolean;
  setClearOldDataBeforeScan: (val: boolean) => void;
  hasExistingResults: boolean;
  totalAllBytes: number;
  onPickFolder: () => void;
  onStartScan: () => void;
  onOpenResults: () => void;
}

export default function HomePage({
  folderPath,
  isDraggingFolder,
  onDragStateChange,
  onDropPath,
  runAiClusterToo,
  setRunAiClusterToo,
  clearOldDataBeforeScan,
  setClearOldDataBeforeScan,
  hasExistingResults,
  totalAllBytes,
  onPickFolder,
  onStartScan,
  onOpenResults,
}: HomePageProps) {
  const { t, formatBytes, isWindows } = useI18n();

  const folderShortName = folderPath
    ? folderPath.split(/[\\/]/).filter(Boolean).pop() || folderPath
    : "";

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isDraggingFolder) {
      onDragStateChange(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
      onDragStateChange(false);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    onDragStateChange(false);
    const firstFile = e.dataTransfer?.files?.[0] as
      | (File & { path?: string })
      | undefined;
    if (firstFile?.path && onDropPath) {
      onDropPath(firstFile.path);
    }
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className="h-screen w-screen bg-[#161618] text-[#F2F2F7] flex flex-col justify-between overflow-hidden select-none"
    >
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

        <div className="flex items-center gap-2">
          {hasExistingResults && (
            <button
              type="button"
              onClick={onOpenResults}
              className="bg-[#2C2C2E] hover:bg-[#3A3A3C] text-[#E5E5EA] hover:text-white text-[12px] px-3 py-1 rounded-[7px] font-medium inline-flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <IconPhotoStack className="w-[14px] h-[14px] text-[#0A84FF]" />
              <span>
                {t.home.viewPreviousResults(formatBytes(totalAllBytes))}
              </span>
            </button>
          )}
          <LanguageSwitcher compact />
        </div>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center px-6 py-4 overflow-y-auto">
        <div className="w-full max-w-md flex flex-col items-center text-center">
          <h1 className="text-2xl lg:text-[26px] font-semibold tracking-tight text-[#F2F2F7] mb-2">
            {t.home.heroTitle}
          </h1>
          <p className="text-[13px] text-[#8E8E93] max-w-md mb-6 leading-relaxed">
            {t.home.heroSubtitle}
          </p>

          {/* Native macOS Finder / Photos Dropzone Panel */}
          <div
            onClick={onPickFolder}
            className={`w-full max-w-md rounded-2xl p-8 flex flex-col items-center justify-center cursor-pointer transition-colors ${
              isDraggingFolder
                ? "bg-[#0A84FF]/[0.08] border border-dashed border-[#0A84FF]"
                : folderPath
                ? "bg-[#1E1E20] border border-dashed border-[#0A84FF]/60 hover:border-[#0A84FF]"
                : "bg-[#1E1E20] border border-dashed border-white/[0.14] hover:border-[#0A84FF]"
            }`}
          >
            <div
              className={`w-12 h-12 rounded-xl flex items-center justify-center mb-3.5 transition-colors ${
                isDraggingFolder
                  ? "bg-[#0A84FF]/20 border border-[#0A84FF]/45 text-[#0A84FF]"
                  : "bg-[#0A84FF]/12 border border-[#0A84FF]/25 text-[#0A84FF]"
              }`}
            >
              <IconFolder className="w-6 h-6" strokeWidth={1.6} />
            </div>

            {!folderPath ? (
              <>
                <span className="text-[15px] font-semibold text-[#F2F2F7] tracking-tight">
                  {isDraggingFolder
                    ? t.home.dropFolderActive
                    : t.home.pickFolderTitle}
                </span>
                <span className="text-[12.5px] text-[#8E8E93] mt-1 leading-snug">
                  {t.home.pickFolderHint}
                </span>
              </>
            ) : (
              <>
                <span className="text-[11px] uppercase tracking-wider text-[#0A84FF] font-semibold mb-1">
                  {t.home.selectedFolderLabel}
                </span>
                <span className="text-[15px] font-semibold text-[#F2F2F7] max-w-full truncate px-2">
                  {folderShortName}
                </span>
                <span
                  className="text-[11.5px] text-[#8E8E93] max-w-full truncate mt-0.5 px-2"
                  title={folderPath}
                >
                  {folderPath}
                </span>
                <span className="bg-[#2C2C2E] hover:bg-[#3A3A3C] text-[11.5px] text-[#E5E5EA] px-3 py-1 rounded-[6px] mt-3.5 font-medium transition-colors">
                  {isDraggingFolder
                    ? t.home.dropFolderActive
                    : t.home.changeFolderLink}
                </span>
              </>
            )}
          </div>

          {/* Native macOS Grouped Preference Rows */}
          <div className="w-full max-w-md mt-3.5 bg-[#1E1E20] border border-white/[0.07] rounded-xl divide-y divide-white/[0.06] overflow-hidden text-left">
            <div
              onClick={() => setRunAiClusterToo(!runAiClusterToo)}
              className="flex items-center gap-3 px-4 py-2.5 hover:bg-white/[0.03] transition-colors cursor-pointer"
            >
              <CustomCheckbox checked={runAiClusterToo} size="sm" />
              <span className="text-[13px] text-[#E5E5EA] font-normal">
                {t.home.optFindSimilar}
              </span>
            </div>

            <div
              onClick={() =>
                setClearOldDataBeforeScan(!clearOldDataBeforeScan)
              }
              className="flex items-center gap-3 px-4 py-2.5 hover:bg-white/[0.03] transition-colors cursor-pointer"
            >
              <CustomCheckbox checked={clearOldDataBeforeScan} size="sm" />
              <span className="text-[13px] text-[#E5E5EA] font-normal">
                {t.home.optClearOld}
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={onStartScan}
            className="mt-5 w-full max-w-md bg-[#007AFF] hover:bg-[#0071EB] active:bg-[#0062CC] py-2.5 px-6 rounded-[9px] font-medium text-[13.5px] text-white shadow-sm transition-colors cursor-pointer"
          >
            {folderPath ? t.home.btnStartScan : t.home.btnPickAndScan}
          </button>
        </div>
      </main>

      <footer className="pb-4 px-6 text-center text-[11.5px] text-[#636366] shrink-0">
        {t.home.privacyFooter}
      </footer>
    </div>
  );
}
