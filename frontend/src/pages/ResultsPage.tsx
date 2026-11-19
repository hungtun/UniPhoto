import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  PhotoItem,
  openPhotoOnMacApi,
  openMultiplePhotosOnMacApi,
} from "../api/PhotoApi";
import CustomCheckbox from "../components/CustomCheckbox";
import LanguageSwitcher from "../components/LanguageSwitcher";
import {
  IconArrowDownCircle,
  IconCheckCircle,
  IconChevronDown,
  IconChevronRight,
  IconClose,
  IconDuplicates,
  IconEye,
  IconFinder,
  IconFolder,
  IconGrid,
  IconKeyboard,
  IconPhotoStack,
  IconQuestionCircle,
  IconRefresh,
  IconSearch,
  IconSidebarLeft,
  IconSimilars,
  IconSingle,
  IconSort,
  IconSparkles,
  IconTrash,
  IconWand,
  IconWarning,
} from "../components/MacIcons";
import { useI18n } from "../i18n/I18nContext";
import { FALLBACK_APP_VERSION, UpdateInfo } from "../utils/updater";
import {
  BestReasonKey,
  SidebarFilter,
  SortMode,
  UnifiedGroup,
  ViewLayout,
  formatQualityScore,
  getAestheticScoreToneClasses,
  getAestheticTagToneClasses,
  getBestPhotoReasonKey,
  isAestheticWarningTag,
} from "../utils/photoHelpers";

interface ResultsPageProps {
  unifiedDupGroups: UnifiedGroup[];
  unifiedSimGroups: UnifiedGroup[];
  totalDupGroups?: number;
  totalDupBytes?: number;
  totalDupPhotos?: number;
  totalSimGroups?: number;
  totalSimBytes?: number;
  totalSimPhotos?: number;
  hasMoreDups?: boolean;
  hasMoreSims?: boolean;
  isLoadingMoreDups?: boolean;
  isLoadingMoreSims?: boolean;
  onLoadMoreDups?: () => void;
  onLoadMoreSims?: () => void;
  disconnectedVolumes?: string[];
  selectedPhotoIds: Set<number>;
  setSelectedPhotoIds: React.Dispatch<React.SetStateAction<Set<number>>>;
  expandedGroups: Record<string, boolean>;
  setExpandedGroups: React.Dispatch<
    React.SetStateAction<Record<string, boolean>>
  >;
  sidebarFilter: SidebarFilter;
  setSidebarFilter: (filter: SidebarFilter) => void;
  isCleaning: boolean;
  isModalOpen?: boolean;
  appVersion?: string;
  updateInfo?: UpdateInfo | null;
  isCheckingUpdate?: boolean;
  onOpenUpdateModal?: () => void;
  onManualCheckUpdate?: () => void;
  onOpenTutorial?: () => void;
  onBackHome: () => void;
  onRefresh: () => void;
  onRunAiCluster: () => void;
  onRunAestheticScore: () => void;
  onSmartCleanup: () => void;
}

export default function ResultsPage({
  unifiedDupGroups,
  unifiedSimGroups,
  totalDupGroups,
  totalDupBytes,
  totalDupPhotos,
  totalSimGroups,
  totalSimBytes,
  totalSimPhotos,
  hasMoreDups = false,
  hasMoreSims = false,
  isLoadingMoreDups = false,
  isLoadingMoreSims = false,
  onLoadMoreDups,
  onLoadMoreSims,
  disconnectedVolumes = [],
  selectedPhotoIds,
  setSelectedPhotoIds,
  expandedGroups,
  setExpandedGroups,
  sidebarFilter,
  setSidebarFilter,
  isCleaning,
  isModalOpen = false,
  appVersion = FALLBACK_APP_VERSION,
  updateInfo = null,
  isCheckingUpdate = false,
  onOpenUpdateModal,
  onManualCheckUpdate,
  onOpenTutorial,
  onBackHome,
  onRefresh,
  onRunAiCluster,
  onRunAestheticScore,
  onSmartCleanup,
}: ResultsPageProps) {
  const { lang, t, formatBytes, isWindows } = useI18n();

  const [activeGroupKey, setActiveGroupKey] = useState<string>("");
  const [activePhotoId, setActivePhotoId] = useState<number | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("size");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [viewLayout, setViewLayout] = useState<ViewLayout>("single");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [isAestheticBannerDismissed, setIsAestheticBannerDismissed] =
    useState<boolean>(false);
  const [isShortcutsOpen, setIsShortcutsOpen] = useState<boolean>(false);
  const shortcutsContainerRef = useRef<HTMLDivElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  const simClusterSignature = useMemo(
    () => unifiedSimGroups.map((g) => g.key).join(","),
    [unifiedSimGroups]
  );

  useEffect(() => {
    setIsAestheticBannerDismissed(false);
  }, [simClusterSignature]);

  const hasAnyAestheticScores = useMemo(
    () =>
      unifiedSimGroups.some(
        (g) =>
          Boolean(g.hasAestheticScores) ||
          g.photos.some(
            (p) =>
              p.aesthetic_score !== null && p.aesthetic_score !== undefined
          )
      ),
    [unifiedSimGroups]
  );

  const isSimPhotoScored = (
    groupKind: "duplicates" | "similars",
    photo?: PhotoItem
  ): boolean =>
    groupKind === "similars" &&
    photo !== undefined &&
    photo.aesthetic_score !== null &&
    photo.aesthetic_score !== undefined;

  const getReasonText = (key: BestReasonKey): string => {
    switch (key) {
      case "highest_res":
        return t.results.reasonHighestRes;
      case "sharpest":
        return t.results.reasonSharpest;
      case "best_exposure":
        return t.results.reasonBestExposure;
      case "best_contrast":
        return t.results.reasonBestContrast;
      case "least_compressed":
        return t.results.reasonLeastCompressed;
      case "eyes_open":
        return t.results.reasonEyesOpen;
      case "level_camera":
        return t.results.reasonLevelCamera;
      case "face_sharp":
        return t.results.reasonFaceSharp;
      case "better_composition":
        return t.results.reasonBetterComposition;
      case "best_aesthetics":
        return t.results.reasonBestAesthetics;
      case "largest_file":
        return t.results.reasonLargestFile;
      case "keep_default":
        return t.results.recommendedKeepBadge;
      default:
        return t.results.reasonBestOverall;
    }
  };

  const formatAestheticTagLabel = (tag: string, photo: PhotoItem): string => {
    const tagMap = t.results.aestheticTags as Record<string, string>;
    const baseLabel = tagMap[tag] ?? tag;
    if (
      tag === "tilted_horizon" &&
      photo.tilt_angle !== null &&
      photo.tilt_angle !== undefined &&
      Math.abs(photo.tilt_angle) >= 1.8
    ) {
      const deg = formatQualityScore(Math.abs(photo.tilt_angle), lang, 1);
      return `${baseLabel} • ${t.results.tiltDeg(deg)}`;
    }
    return baseLabel;
  };

  const photoMap = useMemo(() => {
    const map = new Map<number, PhotoItem>();
    unifiedDupGroups.forEach((g) => g.photos.forEach((p) => map.set(p.id, p)));
    unifiedSimGroups.forEach((g) => g.photos.forEach((p) => map.set(p.id, p)));
    return map;
  }, [unifiedDupGroups, unifiedSimGroups]);

  const loadedDuplicatesBytes = useMemo(
    () => unifiedDupGroups.reduce((s, g) => s + g.totalBytes, 0),
    [unifiedDupGroups]
  );

  const loadedSimilarsBytes = useMemo(
    () => unifiedSimGroups.reduce((s, g) => s + g.totalBytes, 0),
    [unifiedSimGroups]
  );

  const serverTotalDuplicatesBytes = totalDupBytes ?? loadedDuplicatesBytes;
  const serverTotalSimilarsBytes = totalSimBytes ?? loadedSimilarsBytes;

  const totalSelectedBytes = useMemo(() => {
    let bytes = 0;
    selectedPhotoIds.forEach((id) => {
      const p = photoMap.get(id);
      if (p) bytes += p.file_size;
    });
    return bytes;
  }, [selectedPhotoIds, photoMap]);

  const totalAllBytes = serverTotalDuplicatesBytes + serverTotalSimilarsBytes;
  const serverTotalFilesCount =
    (totalDupPhotos ?? 0) + (totalSimPhotos ?? 0) || photoMap.size;

  const handleGroupListScroll = useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      if (searchQuery.trim()) return;
      const el = e.currentTarget;
      if (el.scrollTop + el.clientHeight >= el.scrollHeight - 260) {
        if (
          sidebarFilter === "duplicates" &&
          hasMoreDups &&
          !isLoadingMoreDups &&
          onLoadMoreDups
        ) {
          onLoadMoreDups();
        } else if (
          sidebarFilter === "similars" &&
          hasMoreSims &&
          !isLoadingMoreSims &&
          onLoadMoreSims
        ) {
          onLoadMoreSims();
        }
      }
    },
    [
      searchQuery,
      sidebarFilter,
      hasMoreDups,
      isLoadingMoreDups,
      onLoadMoreDups,
      hasMoreSims,
      isLoadingMoreSims,
      onLoadMoreSims,
    ]
  );

  const currentTabHasMore =
    !searchQuery.trim() &&
    ((sidebarFilter === "duplicates" && hasMoreDups) ||
      (sidebarFilter === "similars" && hasMoreSims));
  const currentTabIsLoadingMore =
    sidebarFilter === "duplicates"
      ? isLoadingMoreDups
      : sidebarFilter === "similars"
      ? isLoadingMoreSims
      : false;
  const currentTabLoadedCount =
    sidebarFilter === "duplicates"
      ? unifiedDupGroups.length
      : unifiedSimGroups.length;
  const currentTabTotalCount =
    sidebarFilter === "duplicates"
      ? totalDupGroups ?? unifiedDupGroups.length
      : totalSimGroups ?? unifiedSimGroups.length;
  const handleLoadMoreCurrentTab =
    sidebarFilter === "duplicates" ? onLoadMoreDups : onLoadMoreSims;

  const displayedGroups: UnifiedGroup[] = useMemo(() => {
    let base: UnifiedGroup[] = [];
    if (sidebarFilter === "duplicates") {
      base = unifiedDupGroups;
    } else if (sidebarFilter === "similars") {
      base = unifiedSimGroups;
    } else {
      const combined = [...unifiedDupGroups, ...unifiedSimGroups];
      const seenKeys = new Set<string>();
      base = combined.filter((g) => {
        if (seenKeys.has(g.key)) return false;
        const hasChecked = g.photos.some((p) => selectedPhotoIds.has(p.id));
        if (hasChecked) seenKeys.add(g.key);
        return hasChecked;
      });
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      base = base.filter(
        (g) =>
          g.title.toLowerCase().includes(q) ||
          g.photos.some(
            (p) =>
              p.file_name.toLowerCase().includes(q) ||
              p.folder_name.toLowerCase().includes(q)
          )
      );
    }

    return [...base].sort((a, b) => {
      if (sortMode === "size") return b.totalBytes - a.totalBytes;
      return b.photos.length - a.photos.length;
    });
  }, [
    sidebarFilter,
    unifiedDupGroups,
    unifiedSimGroups,
    selectedPhotoIds,
    searchQuery,
    sortMode,
  ]);

  const masterHeaderTitle =
    sidebarFilter === "duplicates"
      ? t.results.navAllDuplicates
      : sidebarFilter === "similars"
      ? t.results.navAllSimilars
      : t.results.navSelected;

  const masterGroupCount = useMemo(() => {
    if (searchQuery.trim() || sidebarFilter === "selected") {
      return displayedGroups.length;
    }
    if (sidebarFilter === "duplicates") {
      return totalDupGroups ?? displayedGroups.length;
    }
    return totalSimGroups ?? displayedGroups.length;
  }, [
    searchQuery,
    sidebarFilter,
    displayedGroups.length,
    totalDupGroups,
    totalSimGroups,
  ]);

  const masterTotalBytes = useMemo(() => {
    if (searchQuery.trim()) {
      return displayedGroups.reduce((s, g) => s + g.totalBytes, 0);
    }
    if (sidebarFilter === "duplicates") {
      return serverTotalDuplicatesBytes;
    }
    if (sidebarFilter === "similars") {
      return serverTotalSimilarsBytes;
    }
    return totalSelectedBytes;
  }, [
    searchQuery,
    displayedGroups,
    sidebarFilter,
    serverTotalDuplicatesBytes,
    serverTotalSimilarsBytes,
    totalSelectedBytes,
  ]);

  const currentGroup: UnifiedGroup | undefined = useMemo(() => {
    return (
      displayedGroups.find((g) => g.key === activeGroupKey) ||
      displayedGroups[0]
    );
  }, [displayedGroups, activeGroupKey]);

  const currentPhoto: PhotoItem | undefined = useMemo(() => {
    if (!currentGroup) return undefined;
    return (
      currentGroup.photos.find((p) => p.id === activePhotoId) ||
      currentGroup.photos[0]
    );
  }, [currentGroup, activePhotoId]);

  const groupBestReasonKey = useMemo<BestReasonKey | null>(() => {
    if (!currentGroup || currentGroup.photos.length === 0) return null;
    const best = currentGroup.photos[0];
    const runnerUp = currentGroup.photos[1];
    return getBestPhotoReasonKey(best, runnerUp, currentGroup.kind);
  }, [currentGroup]);

  const groupBestReasonText = useMemo(() => {
    if (!groupBestReasonKey) return "";
    return getReasonText(groupBestReasonKey);
  }, [groupBestReasonKey, lang, t]);

  const isCurrentPhotoBest = useMemo(() => {
    if (!currentGroup || !currentPhoto) return false;
    return (
      currentPhoto.is_best || currentGroup.photos[0]?.id === currentPhoto.id
    );
  }, [currentGroup, currentPhoto]);

  const currentPhotoHasAesthetic =
    currentGroup !== undefined &&
    isSimPhotoScored(currentGroup.kind, currentPhoto);

  useEffect(() => {
    if (currentGroup && currentGroup.key !== activeGroupKey) {
      setActiveGroupKey(currentGroup.key);
      setActivePhotoId(currentGroup.photos[0]?.id ?? null);
    }
  }, [currentGroup, activeGroupKey]);

  const toggleSelectPhoto = useCallback(
    (photoId: number, e?: React.MouseEvent) => {
      if (e) e.stopPropagation();
      setSelectedPhotoIds((prev) => {
        const next = new Set(prev);
        if (next.has(photoId)) {
          next.delete(photoId);
        } else {
          next.add(photoId);
        }
        return next;
      });
    },
    [setSelectedPhotoIds]
  );

  const toggleExpandGroup = (groupKey: string) => {
    setExpandedGroups((prev) => ({
      ...prev,
      [groupKey]: !prev[groupKey],
    }));
  };

  const handleAutoSelectCurrentTab = useCallback(() => {
    setSelectedPhotoIds((prev) => {
      const next = new Set(prev);
      displayedGroups.forEach((g) => {
        g.photos.forEach((p, idx) => {
          const isBest = p.is_best || idx === 0;
          if (isBest) {
            next.delete(p.id);
          } else {
            next.add(p.id);
          }
        });
      });
      return next;
    });
  }, [displayedGroups, setSelectedPhotoIds]);

  const handleDeselectAll = () => {
    setSelectedPhotoIds(new Set());
  };

  useEffect(() => {
    if (!isShortcutsOpen) return;
    const handlePointerDown = (e: MouseEvent) => {
      if (
        shortcutsContainerRef.current &&
        !shortcutsContainerRef.current.contains(e.target as Node)
      ) {
        setIsShortcutsOpen(false);
      }
    };
    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, [isShortcutsOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isModalOpen) return;

      if (!e.altKey && (e.metaKey || e.ctrlKey)) {
        if (e.key === "f" || e.key === "F") {
          e.preventDefault();
          searchInputRef.current?.focus();
          searchInputRef.current?.select();
          return;
        }
      }

      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }

      if (e.altKey) return;

      if (e.metaKey || e.ctrlKey) {
        if (e.key === "a" || e.key === "A") {
          e.preventDefault();
          handleAutoSelectCurrentTab();
        }
        return;
      }

      if (e.key === "ArrowLeft") {
        if (!currentGroup || currentGroup.photos.length === 0) return;
        e.preventDefault();
        const idx = currentGroup.photos.findIndex(
          (p) => p.id === currentPhoto?.id
        );
        const prevIdx = idx > 0 ? idx - 1 : 0;
        const targetPhoto = currentGroup.photos[prevIdx];
        if (targetPhoto) {
          setActivePhotoId(targetPhoto.id);
        }
        return;
      }

      if (e.key === "ArrowRight") {
        if (!currentGroup || currentGroup.photos.length === 0) return;
        e.preventDefault();
        const idx = currentGroup.photos.findIndex(
          (p) => p.id === currentPhoto?.id
        );
        const nextIdx =
          idx >= 0 && idx < currentGroup.photos.length - 1
            ? idx + 1
            : currentGroup.photos.length - 1;
        const targetPhoto = currentGroup.photos[nextIdx];
        if (targetPhoto) {
          setActivePhotoId(targetPhoto.id);
        }
        return;
      }

      if (e.key === "ArrowUp") {
        if (displayedGroups.length === 0) return;
        e.preventDefault();
        const gIdx = displayedGroups.findIndex(
          (g) => g.key === currentGroup?.key
        );
        const prevGIdx = gIdx > 0 ? gIdx - 1 : 0;
        const targetGroup = displayedGroups[prevGIdx];
        if (targetGroup) {
          setActiveGroupKey(targetGroup.key);
          setActivePhotoId(targetGroup.photos[0]?.id ?? null);
        }
        return;
      }

      if (e.key === "ArrowDown") {
        if (displayedGroups.length === 0) return;
        e.preventDefault();
        const gIdx = displayedGroups.findIndex(
          (g) => g.key === currentGroup?.key
        );
        const nextGIdx =
          gIdx >= 0 && gIdx < displayedGroups.length - 1
            ? gIdx + 1
            : displayedGroups.length - 1;
        const targetGroup = displayedGroups[nextGIdx];
        if (targetGroup) {
          setActiveGroupKey(targetGroup.key);
          setActivePhotoId(targetGroup.photos[0]?.id ?? null);
        }
        return;
      }

      if (e.key === " ") {
        e.preventDefault();
        if (currentPhoto) {
          toggleSelectPhoto(currentPhoto.id);
        }
        return;
      }

      if (e.key === "1") {
        e.preventDefault();
        setViewLayout("single");
        return;
      }

      if (e.key === "2") {
        e.preventDefault();
        setViewLayout("grid");
        return;
      }

      if (e.key === "p" || e.key === "P" || e.key === "Enter") {
        if (!currentPhoto) return;
        e.preventDefault();
        openPhotoOnMacApi(currentPhoto.id, "preview");
        return;
      }

      if (e.key === "f" || e.key === "F") {
        if (!currentPhoto) return;
        e.preventDefault();
        openPhotoOnMacApi(currentPhoto.id, "finder");
        return;
      }

      if (e.key === "Escape") {
        if (isShortcutsOpen) {
          e.preventDefault();
          setIsShortcutsOpen(false);
        } else if (searchQuery) {
          e.preventDefault();
          setSearchQuery("");
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    isModalOpen,
    currentGroup,
    currentPhoto,
    displayedGroups,
    isShortcutsOpen,
    searchQuery,
    handleAutoSelectCurrentTab,
    toggleSelectPhoto,
  ]);

  const selectedInCurrentGroup = currentGroup
    ? currentGroup.photos.filter((p) => selectedPhotoIds.has(p.id)).length
    : 0;

  const renderAestheticTagPills = (photo: PhotoItem, compact = false) => {
    const tags = photo.aesthetic_tags;
    if (!tags || tags.length === 0) return null;
    const sizeCls = compact
      ? "text-[10px] px-2 py-0.5 gap-1"
      : "text-[11px] px-2.5 py-0.5 gap-1";

    return (
      <div className="flex flex-wrap items-center gap-1.5">
        {tags.map((tag) => {
          const warning = isAestheticWarningTag(tag);
          return (
            <span
              key={tag}
              className={`inline-flex items-center rounded-md border font-medium whitespace-nowrap ${sizeCls} ${getAestheticTagToneClasses(
                tag
              )}`}
            >
              {warning ? (
                <IconWarning className="w-3 h-3 shrink-0" />
              ) : (
                <IconCheckCircle className="w-3 h-3 shrink-0" />
              )}
              <span>{formatAestheticTagLabel(tag, photo)}</span>
            </span>
          );
        })}
      </div>
    );
  };

  const getAestheticMetricItems = (photo: PhotoItem) => {
    const items: Array<{
      key: string;
      label: string;
      value: number;
      barClass: string;
    }> = [];

    if (
      photo.composition_score !== null &&
      photo.composition_score !== undefined
    ) {
      items.push({
        key: "composition",
        label: t.results.metricComposition,
        value: photo.composition_score,
        barClass: "bg-[#5E5CE6]",
      });
    }

    if (photo.face_score !== null && photo.face_score !== undefined) {
      items.push({
        key: "face",
        label: t.results.metricFace,
        value: photo.face_score,
        barClass: photo.has_closed_eyes ? "bg-[#FF453A]" : "bg-[#30D158]",
      });
    }

    return items;
  };

  const storageFillPercent =
    totalAllBytes > 0
      ? Math.min(100, Math.round((totalSelectedBytes / totalAllBytes) * 100))
      : 0;

  return (
    <div className="h-screen w-screen flex overflow-hidden select-none text-[#F2F2F7]">
      {/* ============================================================
          PANE 1: NATIVE MACOS VIBRANCY SOURCE-LIST SIDEBAR
         ============================================================ */}
      {!isSidebarCollapsed && (
        <aside
          className={`uniphoto-sidebar w-[232px] shrink-0 flex flex-col justify-between border-r border-white/[0.09] ${
            isWindows
              ? "bg-[#202024]"
              : "bg-[#252528]/78 backdrop-blur-2xl"
          }`}
        >
          <div>
            {/* Traffic-Light Safe Zone (macOS) / Standard Padding (Windows) + Sidebar Collapse Toggle */}
            <div
              data-tauri-drag-region
              className={`h-[46px] ${
                isWindows ? "pl-3.5" : "pl-[78px]"
              } pr-3 flex items-center justify-end shrink-0`}
            >
              <button
                type="button"
                onClick={() => setIsSidebarCollapsed(true)}
                title={t.results.btnHideSidebar}
                aria-label={t.results.btnHideSidebar}
                className="w-7 h-7 rounded-md hover:bg-white/[0.09] text-[#AEAEB2] hover:text-white flex items-center justify-center transition-colors cursor-pointer"
              >
                <IconSidebarLeft className="w-[16px] h-[16px]" />
              </button>
            </div>

            {/* Primary Source List */}
            <nav className="px-2.5 space-y-0.5">
              <button
                type="button"
                onClick={() => setSidebarFilter("duplicates")}
                className={`w-full rounded-[8px] px-2.5 py-[7px] text-[13px] flex items-center gap-2.5 transition-colors cursor-pointer ${
                  sidebarFilter === "duplicates"
                    ? "bg-[#007AFF] text-white font-medium"
                    : "text-[#E5E5EA] hover:bg-white/[0.06]"
                }`}
              >
                <IconDuplicates
                  className={`w-[16px] h-[16px] shrink-0 ${
                    sidebarFilter === "duplicates"
                      ? "text-white"
                      : "text-[#0A84FF]"
                  }`}
                />
                <span className="truncate flex-1 text-left">
                  {t.results.navAllDuplicates}
                </span>
                <span
                  className={`text-[12px] tabular-nums shrink-0 ${
                    sidebarFilter === "duplicates"
                      ? "text-white/85"
                      : "text-[#8E8E93]"
                  }`}
                >
                  {formatBytes(serverTotalDuplicatesBytes)}
                </span>
              </button>

              <button
                type="button"
                onClick={() => setSidebarFilter("similars")}
                className={`w-full rounded-[8px] px-2.5 py-[7px] text-[13px] flex items-center gap-2.5 transition-colors cursor-pointer ${
                  sidebarFilter === "similars"
                    ? "bg-[#007AFF] text-white font-medium"
                    : "text-[#E5E5EA] hover:bg-white/[0.06]"
                }`}
              >
                <IconSimilars
                  className={`w-[16px] h-[16px] shrink-0 ${
                    sidebarFilter === "similars"
                      ? "text-white"
                      : "text-[#0A84FF]"
                  }`}
                />
                <span className="truncate flex-1 text-left">
                  {t.results.navAllSimilars}
                </span>
                <span
                  className={`text-[12px] tabular-nums shrink-0 ${
                    sidebarFilter === "similars"
                      ? "text-white/85"
                      : "text-[#8E8E93]"
                  }`}
                >
                  {formatBytes(serverTotalSimilarsBytes)}
                </span>
              </button>

              <button
                type="button"
                onClick={() => setSidebarFilter("selected")}
                className={`w-full rounded-[8px] px-2.5 py-[7px] text-[13px] flex items-center gap-2.5 transition-colors cursor-pointer ${
                  sidebarFilter === "selected"
                    ? "bg-[#007AFF] text-white font-medium"
                    : "text-[#E5E5EA] hover:bg-white/[0.06]"
                }`}
              >
                <IconCheckCircle
                  className={`w-[16px] h-[16px] shrink-0 ${
                    sidebarFilter === "selected"
                      ? "text-white"
                      : "text-[#0A84FF]"
                  }`}
                />
                <span className="truncate flex-1 text-left">
                  {t.results.navSelected}
                </span>
                <span
                  className={`text-[12px] tabular-nums shrink-0 ${
                    sidebarFilter === "selected"
                      ? "text-white/85"
                      : "text-[#8E8E93]"
                  }`}
                >
                  {selectedPhotoIds.size}
                </span>
              </button>
            </nav>

            {/* Storage & Library Actions Section */}
            <div className="px-2.5 pt-5">
              <p className="px-2 text-[11px] font-medium text-[#8E8E93] mb-1">
                {t.results.secStorage}
              </p>

              <div className="space-y-0.5">
                <button
                  type="button"
                  onClick={onBackHome}
                  className="w-full rounded-[8px] px-2.5 py-[6px] text-[13px] text-[#E5E5EA] hover:bg-white/[0.06] flex items-center gap-2.5 transition-colors cursor-pointer text-left"
                >
                  <IconFolder className="w-[16px] h-[16px] text-[#0A84FF] shrink-0" />
                  <span className="truncate">{t.results.btnChangeFolder}</span>
                </button>

                <button
                  type="button"
                  onClick={onRunAiCluster}
                  className="w-full rounded-[8px] px-2.5 py-[6px] text-[13px] text-[#E5E5EA] hover:bg-white/[0.06] flex items-center gap-2.5 transition-colors cursor-pointer text-left"
                >
                  <IconSparkles className="w-[16px] h-[16px] text-[#0A84FF] shrink-0" />
                  <span className="truncate">{t.results.btnFindSimilars}</span>
                </button>
              </div>

              <div className="px-2 pt-2.5">
                <p className="text-[11px] text-[#8E8E93] tabular-nums truncate">
                  {t.results.selectedLabel} {formatBytes(totalSelectedBytes)} /{" "}
                  {formatBytes(totalAllBytes)}
                </p>
                <div className="mt-1.5 w-full h-[3px] rounded-full bg-white/[0.12] overflow-hidden">
                  <div
                    className="h-full bg-[#FFD60A] transition-all duration-300 rounded-full"
                    style={{ width: `${storageFillPercent}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="shrink-0">
            {updateInfo?.hasUpdate && (
              <div
                role="button"
                tabIndex={0}
                onClick={onOpenUpdateModal}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onOpenUpdateModal?.();
                  }
                }}
                className="mx-2.5 mb-2 rounded-[9px] px-2.5 py-2 bg-[#0A84FF]/[0.14] hover:bg-[#0A84FF]/[0.22] border border-[#0A84FF]/35 flex items-center gap-2 transition-colors cursor-pointer"
              >
                <IconArrowDownCircle className="w-[16px] h-[16px] text-[#64D2FF] shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[12px] font-medium text-[#F2F2F7] leading-tight truncate">
                      {t.update.badgeAvailable(updateInfo.latestVersion)}
                    </span>
                    <span className="w-1.5 h-1.5 rounded-full bg-[#30D158] shrink-0" />
                  </div>
                  <p className="text-[10.5px] text-[#AEAEB2] leading-tight mt-0.5 truncate">
                    {t.update.sidebarUpdateSub}
                  </p>
                </div>
              </div>
            )}

            {/* Bottom Pinned Status Footer */}
            <div className="px-2.5 py-2.5 border-t border-white/[0.07] flex items-center justify-between gap-1.5 shrink-0">
              <div className="flex items-center gap-1.5 min-w-0">
                <div className="w-6 h-6 rounded-full bg-[#323236] border border-white/10 flex items-center justify-center shrink-0 overflow-hidden">
                  <img
                    src="/logo.png"
                    alt="UniPhoto"
                    className="w-3.5 h-3.5 object-contain"
                    onError={(e) => {
                      e.currentTarget.style.display = "none";
                    }}
                  />
                </div>
                <div className="min-w-0">
                  <p className="text-[11.5px] font-medium text-white leading-tight truncate">
                    UniPhoto{" "}
                    <span className="text-[10px] font-normal text-[#8E8E93] tabular-nums">
                      v{appVersion}
                    </span>
                  </p>
                  <div className="flex items-center gap-1 text-[10.5px] text-[#8E8E93] leading-tight mt-0.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#30D158] shrink-0" />
                    <span className="truncate tabular-nums">
                      {serverTotalFilesCount}{" "}
                      {t.results.footerPhotosSuffix(serverTotalFilesCount)}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-0.5 shrink-0">
                <LanguageSwitcher compact />
                <button
                  type="button"
                  disabled={isCheckingUpdate}
                  onClick={onManualCheckUpdate}
                  title={
                    isCheckingUpdate
                      ? t.update.checkingUpdate
                      : t.update.btnCheckUpdate
                  }
                  aria-label={t.update.btnCheckUpdate}
                  className={`w-6 h-6 rounded-md hover:bg-white/[0.09] flex items-center justify-center transition-colors cursor-pointer disabled:opacity-60 ${
                    updateInfo?.hasUpdate
                      ? "text-[#0A84FF] hover:text-[#64D2FF]"
                      : "text-[#AEAEB2] hover:text-white"
                  }`}
                >
                  <IconArrowDownCircle
                    className={`w-[14px] h-[14px] ${
                      isCheckingUpdate ? "animate-pulse text-[#0A84FF]" : ""
                    }`}
                  />
                </button>
                <button
                  type="button"
                  onClick={onRefresh}
                  title={t.results.btnRefresh}
                  aria-label={t.results.btnRefresh}
                  className="w-6 h-6 rounded-md hover:bg-white/[0.09] text-[#AEAEB2] hover:text-white flex items-center justify-center transition-colors cursor-pointer"
                >
                  <IconRefresh className="w-[14px] h-[14px]" />
                </button>
              </div>
            </div>
          </div>
        </aside>
      )}

      {/* ============================================================
          PANE 2: MIDDLE MASTER LIST COLUMN
         ============================================================ */}
      <section className="w-[295px] lg:w-[320px] shrink-0 flex flex-col bg-[#1E1E20] border-r border-white/[0.08] min-h-0">
        {/* Top Master Header + Capsule Search + Circular Action Buttons */}
        <div
          data-tauri-drag-region
          className="pt-2.5 pb-2.5 px-3.5 border-b border-white/[0.06] shrink-0"
        >
          <div
            data-tauri-drag-region
            className={`min-h-[34px] flex items-center gap-2 ${
              isSidebarCollapsed && !isWindows ? "pl-[76px]" : ""
            }`}
          >
            {isSidebarCollapsed && (
              <button
                type="button"
                onClick={() => setIsSidebarCollapsed(false)}
                title={t.results.btnShowSidebar}
                aria-label={t.results.btnShowSidebar}
                className="w-7 h-7 rounded-md hover:bg-white/[0.09] text-[#AEAEB2] hover:text-white flex items-center justify-center shrink-0 transition-colors cursor-pointer"
              >
                <IconSidebarLeft className="w-[16px] h-[16px]" />
              </button>
            )}

            <div data-tauri-drag-region className="min-w-0 flex-1">
              <h2
                data-tauri-drag-region
                className="text-[14px] font-semibold text-white leading-tight truncate"
              >
                {masterHeaderTitle}
              </h2>
              <p
                data-tauri-drag-region
                className="text-[11px] text-[#8E8E93] mt-0.5 truncate tabular-nums"
              >
                {t.results.masterSubtitle(
                  masterGroupCount,
                  formatBytes(masterTotalBytes)
                )}
              </p>
            </div>

            {isSidebarCollapsed && updateInfo?.hasUpdate && (
              <button
                type="button"
                onClick={onOpenUpdateModal}
                title={t.update.badgeAvailable(updateInfo.latestVersion)}
                className="bg-[#0A84FF]/15 hover:bg-[#0A84FF]/25 border border-[#0A84FF]/35 text-[#64D2FF] text-[11px] px-2 py-0.5 rounded-[6px] font-medium inline-flex items-center gap-1 shrink-0 transition-colors cursor-pointer"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#30D158] shrink-0" />
                <IconArrowDownCircle className="w-[13px] h-[13px] shrink-0" />
                <span className="tabular-nums">
                  v{updateInfo.latestVersion}
                </span>
              </button>
            )}
          </div>

          <div className="mt-2.5 flex items-center gap-1.5">
            <div className="flex-1 min-w-0 relative flex items-center bg-[#2C2C2E] border border-white/[0.05] focus-within:border-[#0A84FF] rounded-full h-[30px] px-2.5 transition-colors">
              <IconSearch className="w-[14px] h-[14px] text-[#8E8E93] shrink-0 mr-1.5" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Escape") {
                    if (searchQuery) {
                      setSearchQuery("");
                    } else {
                      e.currentTarget.blur();
                    }
                  }
                }}
                placeholder={t.results.searchPlaceholder}
                className="w-full bg-transparent text-[12.5px] text-[#F2F2F7] placeholder-[#8E8E93] focus:outline-none min-w-0"
              />
              {searchQuery ? (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  title={t.results.btnClearSearch}
                  aria-label={t.results.btnClearSearch}
                  className="w-4 h-4 rounded-full bg-white/[0.16] hover:bg-white/[0.26] text-[#E5E5EA] flex items-center justify-center shrink-0 ml-1 cursor-pointer"
                >
                  <IconClose className="w-2.5 h-2.5" strokeWidth={2.2} />
                </button>
              ) : (
                <kbd className="text-[10.5px] text-[#636366] font-sans shrink-0 ml-1 pointer-events-none">
                  {isWindows ? "Ctrl+F" : "⌘F"}
                </kbd>
              )}
            </div>

            <button
              type="button"
              onClick={handleAutoSelectCurrentTab}
              title={t.results.btnAutoSelectTooltip}
              aria-label={t.results.btnAutoSelect}
              className="w-[30px] h-[30px] rounded-full bg-[#2C2C2E] hover:bg-[#3A3A3C] flex items-center justify-center text-[#AEAEB2] hover:text-white shrink-0 transition-colors cursor-pointer"
            >
              <IconWand className="w-[14px] h-[14px]" />
            </button>

            <button
              type="button"
              onClick={() =>
                setSortMode((m) => (m === "size" ? "count" : "size"))
              }
              title={
                sortMode === "size"
                  ? t.results.sortBySize
                  : t.results.sortByCount
              }
              aria-label={
                sortMode === "size"
                  ? t.results.sortBySize
                  : t.results.sortByCount
              }
              className={`w-[30px] h-[30px] rounded-full bg-[#2C2C2E] hover:bg-[#3A3A3C] flex items-center justify-center shrink-0 transition-colors cursor-pointer ${
                sortMode === "count"
                  ? "text-[#0A84FF]"
                  : "text-[#AEAEB2] hover:text-white"
              }`}
            >
              <IconSort className="w-[14px] h-[14px]" />
            </button>

            {selectedPhotoIds.size > 0 && (
              <button
                type="button"
                onClick={handleDeselectAll}
                title={t.results.btnDeselectAll}
                aria-label={t.results.btnDeselectAll}
                className="w-[30px] h-[30px] rounded-full bg-[#2C2C2E] hover:bg-[#3A3A3C] flex items-center justify-center text-[#AEAEB2] hover:text-white shrink-0 transition-colors cursor-pointer"
              >
                <IconClose className="w-[13px] h-[13px]" />
              </button>
            )}
          </div>
        </div>

        {/* Scrollable Master Group List with Infinite Scroll */}
        <div
          onScroll={handleGroupListScroll}
          className="flex-1 overflow-y-auto divide-y divide-white/[0.05]"
        >
          {displayedGroups.length === 0 ? (
            <div className="p-8 text-center text-[12.5px] text-[#8E8E93]">
              {t.results.emptyGroups}
            </div>
          ) : (
            displayedGroups.map((group) => {
              const isGroupSelected = currentGroup?.key === group.key;
              const isExpanded = !!expandedGroups[group.key];
              const checkedCount = group.photos.filter((p) =>
                selectedPhotoIds.has(p.id)
              ).length;
              const topPhoto = group.photos[0];
              const topHasAesthetic = isSimPhotoScored(group.kind, topPhoto);

              return (
                <div
                  key={group.key}
                  className={`transition-colors ${
                    isGroupSelected ? "bg-[#2C2C2E]" : "hover:bg-white/[0.04]"
                  }`}
                >
                  <div
                    onClick={() => {
                      setActiveGroupKey(group.key);
                      setActivePhotoId(group.photos[0]?.id ?? null);
                      toggleExpandGroup(group.key);
                    }}
                    className="px-3.5 py-2.5 flex items-center gap-3 cursor-pointer"
                  >
                    <img
                      src={topPhoto?.thumbnail_url}
                      alt=""
                      loading="lazy"
                      className="w-11 h-11 rounded-[10px] object-cover bg-[#252528] shrink-0 border border-white/[0.06]"
                    />

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-[13px] font-medium text-[#F2F2F7] truncate">
                          {group.title}
                        </p>
                        <span className="text-[11px] text-[#8E8E93] tabular-nums shrink-0">
                          {topHasAesthetic && topPhoto ? (
                            <span className="text-[#BF5AF2] font-medium">
                              ✦{" "}
                              {formatQualityScore(
                                topPhoto.aesthetic_score,
                                lang
                              )}
                            </span>
                          ) : (
                            formatBytes(group.totalBytes)
                          )}
                        </span>
                      </div>

                      <div className="flex items-center justify-between gap-2 mt-0.5">
                        <p className="text-[12px] text-[#8E8E93] truncate">
                          {topPhoto?.folder_name
                            ? `${topPhoto.folder_name} • `
                            : ""}
                          {t.results.groupPhotosCount(group.photos.length)}
                        </p>

                        <div className="flex items-center gap-1.5 shrink-0">
                          {checkedCount > 0 && (
                            <span className="inline-flex items-center gap-1 text-[11px] text-[#0A84FF] font-medium tabular-nums">
                              <span className="w-1.5 h-1.5 rounded-full bg-[#0A84FF]" />
                              <span>
                                {checkedCount}/{group.photos.length}
                              </span>
                            </span>
                          )}
                          <span className="text-[#636366]">
                            {isExpanded ? (
                              <IconChevronDown className="w-3 h-3" />
                            ) : (
                              <IconChevronRight className="w-3 h-3" />
                            )}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="bg-[#171719] px-3 py-1.5 space-y-0.5 border-t border-white/[0.05]">
                      {group.photos.map((photo, pIdx) => {
                        const isChecked = selectedPhotoIds.has(photo.id);
                        const isPhotoFocused = currentPhoto?.id === photo.id;
                        const isBest = photo.is_best || pIdx === 0;
                        const photoHasAesthetic = isSimPhotoScored(
                          group.kind,
                          photo
                        );
                        const hasWarning =
                          photoHasAesthetic &&
                          Boolean(
                            photo.has_closed_eyes ||
                              photo.aesthetic_tags?.some(isAestheticWarningTag)
                          );

                        return (
                          <div
                            key={photo.id}
                            onClick={() => {
                              setActiveGroupKey(group.key);
                              setActivePhotoId(photo.id);
                            }}
                            className={`flex items-center gap-2 px-2 py-1.5 rounded-[7px] text-[12px] cursor-pointer transition-colors ${
                              isPhotoFocused
                                ? "bg-[#007AFF]/20 text-white"
                                : "text-[#D1D1D6] hover:bg-white/[0.05]"
                            }`}
                          >
                            <CustomCheckbox
                              size="sm"
                              checked={isChecked}
                              onChange={(e) => toggleSelectPhoto(photo.id, e)}
                            />
                            <span className="truncate flex-1 font-normal">
                              {photo.file_name}
                            </span>
                            {photoHasAesthetic ? (
                              <span
                                title={
                                  photo.quality_score !== null
                                    ? `${
                                        t.results.aestheticScoreLabel
                                      }: ${formatQualityScore(
                                        photo.aesthetic_score,
                                        lang
                                      )} • ${
                                        t.results.scoreLabel
                                      }: ${formatQualityScore(
                                        photo.quality_score,
                                        lang
                                      )}`
                                    : undefined
                                }
                                className={`text-[10.5px] tabular-nums font-medium shrink-0 ${
                                  isBest
                                    ? "text-[#32D74B]"
                                    : hasWarning
                                    ? "text-[#FFD60A]"
                                    : "text-[#BF5AF2]"
                                }`}
                              >
                                ✦{" "}
                                {formatQualityScore(
                                  photo.aesthetic_score,
                                  lang
                                )}
                              </span>
                            ) : (
                              <span className="text-[10.5px] text-[#8E8E93] tabular-nums shrink-0 whitespace-nowrap">
                                {formatBytes(photo.file_size)}
                              </span>
                            )}
                            {isBest && (
                              <span
                                className="text-[9.5px] bg-[#30D158]/16 border border-[#30D158]/35 text-[#32D74B] px-1.5 py-0.5 rounded-[5px] font-medium shrink-0 whitespace-nowrap"
                                title={t.results.badgeKeepTooltip}
                              >
                                {t.results.badgeKeepShort}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })
          )}

          {currentTabHasMore && (
            <div className="px-3.5 py-3 text-center">
              {currentTabIsLoadingMore ? (
                <div className="inline-flex items-center gap-2 text-[11.5px] text-[#8E8E93]">
                  <span className="w-3.5 h-3.5 rounded-full border-2 border-[#0A84FF] border-t-transparent animate-spin shrink-0" />
                  <span>{t.results.loadingMoreGroups}</span>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={handleLoadMoreCurrentTab}
                  className="w-full py-1.5 px-3 rounded-[8px] bg-[#2C2C2E] hover:bg-[#3A3A3C] text-[12px] font-medium text-[#0A84FF] hover:text-white transition-colors cursor-pointer"
                >
                  {t.results.btnLoadMoreGroups(
                    currentTabLoadedCount,
                    currentTabTotalCount
                  )}
                </button>
              )}
            </div>
          )}
        </div>
      </section>

      {/* ============================================================
          PANE 3: RIGHT DETAIL / INSPECTOR WORKSPACE
         ============================================================ */}
      <main className="flex-1 min-w-0 flex flex-col bg-[#161618] overflow-hidden">
        {/* Unified macOS Toolbar */}
        <div
          data-tauri-drag-region
          className="h-[48px] px-4 border-b border-white/[0.07] bg-[#1C1C1E] flex items-center justify-between gap-2 shrink-0"
        >
          <div className="flex items-center gap-1.5 min-w-0 overflow-x-auto">
            {/* Apple NSSegmentedControl */}
            <div className="bg-[#2C2C2E] p-[2px] rounded-[7px] flex items-center shrink-0">
              <button
                type="button"
                onClick={() => setViewLayout("single")}
                className={`whitespace-nowrap rounded-[5px] px-2.5 py-1 text-[12px] inline-flex items-center gap-1.5 transition-colors cursor-pointer ${
                  viewLayout === "single"
                    ? "bg-[#48484A] text-white font-medium shadow-sm"
                    : "text-[#98989D] hover:text-white"
                }`}
              >
                <IconSingle className="w-[14px] h-[14px]" />
                <span>{t.results.viewSingle}</span>
              </button>
              <button
                type="button"
                onClick={() => setViewLayout("grid")}
                className={`whitespace-nowrap rounded-[5px] px-2.5 py-1 text-[12px] inline-flex items-center gap-1.5 transition-colors cursor-pointer ${
                  viewLayout === "grid"
                    ? "bg-[#48484A] text-white font-medium shadow-sm"
                    : "text-[#98989D] hover:text-white"
                }`}
              >
                <IconGrid className="w-[14px] h-[14px]" />
                <span>{t.results.viewGrid}</span>
              </button>
            </div>

            {currentPhoto && (
              <div className="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  onClick={() =>
                    openPhotoOnMacApi(currentPhoto.id, "preview")
                  }
                  className="whitespace-nowrap bg-[#2C2C2E] hover:bg-[#3A3A3C] text-[#E5E5EA] hover:text-white rounded-[6px] px-2.5 py-1 text-[12px] inline-flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <IconEye className="w-[14px] h-[14px] text-[#AEAEB2]" />
                  <span>{t.results.btnOpenPreview}</span>
                </button>
                <button
                  type="button"
                  onClick={() => openPhotoOnMacApi(currentPhoto.id, "finder")}
                  className="whitespace-nowrap bg-[#2C2C2E] hover:bg-[#3A3A3C] text-[#E5E5EA] hover:text-white rounded-[6px] px-2.5 py-1 text-[12px] inline-flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <IconFinder className="w-[14px] h-[14px] text-[#AEAEB2]" />
                  <span>{t.results.btnOpenFinder}</span>
                </button>
                {currentGroup && (
                  <button
                    type="button"
                    onClick={() =>
                      openMultiplePhotosOnMacApi(
                        currentGroup.photos.map((p) => p.id)
                      )
                    }
                    className="whitespace-nowrap bg-[#2C2C2E] hover:bg-[#3A3A3C] text-[#E5E5EA] hover:text-white rounded-[6px] px-2.5 py-1 text-[12px] inline-flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    <IconFolder className="w-[14px] h-[14px] text-[#AEAEB2]" />
                    <span className="hidden xl:inline">
                      {t.results.btnOpenGroup}
                    </span>
                  </button>
                )}
              </div>
            )}

            {sidebarFilter === "similars" && unifiedSimGroups.length > 0 && (
              <button
                type="button"
                onClick={onRunAestheticScore}
                title={t.results.btnScoreAestheticsTooltip}
                className={`whitespace-nowrap shrink-0 rounded-[6px] px-2.5 py-1 text-[12px] font-medium inline-flex items-center gap-1.5 transition-colors cursor-pointer ${
                  hasAnyAestheticScores
                    ? "bg-[#2C2C2E] hover:bg-[#3A3A3C] text-[#E5E5EA] border border-[#5E5CE6]/45"
                    : "bg-[#5E5CE6] hover:bg-[#6E6CF0] text-white"
                }`}
              >
                <IconSparkles className="w-[14px] h-[14px]" />
                <span>
                  {hasAnyAestheticScores
                    ? t.results.btnRescoreAesthetics
                    : t.results.btnScoreAesthetics}
                </span>
              </button>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => {
                setIsShortcutsOpen(false);
                onOpenTutorial?.();
              }}
              title={t.tutorial.btnOpenTutorialTooltip}
              className="whitespace-nowrap inline-flex items-center gap-1.5 text-[12px] px-2.5 py-1 rounded-[6px] bg-[#2C2C2E] hover:bg-[#3A3A3C] text-[#E5E5EA] hover:text-white transition-colors cursor-pointer"
            >
              <IconQuestionCircle className="w-[15px] h-[15px]" />
              <span className="hidden xl:inline">
                {t.tutorial.btnOpenTutorial}
              </span>
            </button>

            <div ref={shortcutsContainerRef} className="relative shrink-0">
              <button
                type="button"
                onClick={() => setIsShortcutsOpen((v) => !v)}
                title={t.results.btnShortcutsTooltip}
                aria-expanded={isShortcutsOpen}
                className={`whitespace-nowrap inline-flex items-center gap-1.5 text-[12px] px-2.5 py-1 rounded-[6px] transition-colors cursor-pointer ${
                  isShortcutsOpen
                    ? "bg-[#3A3A3C] text-white font-medium"
                    : "bg-[#2C2C2E] hover:bg-[#3A3A3C] text-[#E5E5EA] hover:text-white"
                }`}
              >
                <IconKeyboard className="w-[15px] h-[15px]" />
                <span className="hidden xl:inline">
                  {t.results.btnShortcuts}
                </span>
              </button>

              {isShortcutsOpen && (
                <div className="absolute right-0 top-full mt-2 z-50 w-72 sm:w-80 bg-[#262629]/95 backdrop-blur-2xl rounded-xl p-3.5 border border-white/[0.12] shadow-2xl">
                  <div className="flex items-center justify-between gap-2 pb-2 mb-2 border-b border-white/[0.08]">
                    <span className="text-[12px] font-semibold text-white inline-flex items-center gap-1.5">
                      <IconKeyboard className="w-[14px] h-[14px] text-[#0A84FF]" />
                      <span>{t.results.shortcutsTitle}</span>
                    </span>
                    <button
                      type="button"
                      onClick={() => setIsShortcutsOpen(false)}
                      className="w-5 h-5 rounded-md flex items-center justify-center text-[#8E8E93] hover:text-white hover:bg-white/[0.08] cursor-pointer"
                    >
                      <IconClose className="w-3 h-3" />
                    </button>
                  </div>

                  <div className="space-y-1.5 text-[11.5px]">
                    {[
                      {
                        keys: [isWindows ? "Ctrl+F" : "⌘F"],
                        desc: t.results.shortcutSearchFocus,
                      },
                      {
                        keys: ["←", "→"],
                        desc: t.results.shortcutPrevNextPhoto,
                      },
                      {
                        keys: ["↑", "↓"],
                        desc: t.results.shortcutPrevNextGroup,
                      },
                      {
                        keys: ["Space"],
                        desc: t.results.shortcutToggleSelect,
                      },
                      {
                        keys: ["1", "2"],
                        desc: t.results.shortcutSwitchView,
                      },
                      {
                        keys: ["P", "Enter"],
                        desc: t.results.shortcutOpenPreview,
                      },
                      {
                        keys: ["F"],
                        desc: t.results.shortcutRevealFinder,
                      },
                      {
                        keys: [isWindows ? "Ctrl+A" : "⌘A"],
                        desc: t.results.shortcutAutoSelect,
                      },
                      {
                        keys: ["Esc"],
                        desc: t.results.shortcutEscape,
                      },
                    ].map((row) => (
                      <div
                        key={row.keys.join("-")}
                        className="flex items-center justify-between gap-3 py-0.5"
                      >
                        <span className="text-[#AEAEB2] truncate">
                          {row.desc}
                        </span>
                        <div className="flex items-center gap-1 shrink-0">
                          {row.keys.map((k) => (
                            <kbd
                              key={k}
                              className="px-1.5 py-0.5 rounded-[5px] bg-[#3A3A3C] border border-white/[0.10] text-[10px] font-mono font-medium text-white"
                            >
                              {k}
                            </kbd>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Disconnected External Volume Notice Strip */}
        {disconnectedVolumes.length > 0 && (
          <div className="shrink-0 px-4 py-2 bg-[#242426] border-b border-white/[0.07] flex flex-wrap items-center justify-between gap-3 text-[12px]">
            <div className="flex items-center gap-2.5 min-w-0 flex-1">
              <IconWarning className="w-4 h-4 text-[#FFD60A] shrink-0" />
              <span className="text-[#E5E5EA] text-[11.5px] leading-snug">
                {t.results.disconnectedVolumesNotice(
                  disconnectedVolumes.join(", ")
                )}
              </span>
            </div>

            <button
              type="button"
              onClick={onRefresh}
              className="whitespace-nowrap shrink-0 text-[11.5px] font-medium bg-[#323236] hover:bg-[#3A3A3C] text-[#F2F2F7] px-3 py-1 rounded-[6px] inline-flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <IconRefresh className="w-3.5 h-3.5" />
              <span>{t.results.btnRefresh}</span>
            </button>
          </div>
        )}

        {/* Optional Deep Aesthetic Discovery Strip (Unscored Similar Photos Only) */}
        {sidebarFilter === "similars" &&
          unifiedSimGroups.length > 0 &&
          !hasAnyAestheticScores &&
          !isAestheticBannerDismissed && (
            <div className="shrink-0 px-4 py-2 bg-[#242426] border-b border-white/[0.07] flex flex-wrap items-center justify-between gap-3 text-[12px]">
              <div className="flex items-center gap-2.5 min-w-0 flex-1">
                <IconSparkles className="w-4 h-4 text-[#5E5CE6] shrink-0" />
                <div className="min-w-0">
                  <span className="font-medium text-[#F2F2F7] mr-2">
                    {t.results.aestheticBannerTitle}
                  </span>
                  <span className="text-[#8E8E93] text-[11.5px]">
                    {t.results.aestheticBannerDesc}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  type="button"
                  onClick={onRunAestheticScore}
                  title={t.results.btnScoreAestheticsTooltip}
                  className="whitespace-nowrap px-3 py-1 rounded-[6px] text-[11.5px] font-medium bg-[#5E5CE6] hover:bg-[#6E6CF0] text-white inline-flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <IconSparkles className="w-3.5 h-3.5" />
                  <span>{t.results.btnScoreAesthetics}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setIsAestheticBannerDismissed(true)}
                  title={t.results.btnDismissBanner}
                  aria-label={t.results.btnDismissBanner}
                  className="w-6 h-6 rounded-md flex items-center justify-center text-[#8E8E93] hover:text-white hover:bg-white/[0.08] transition-colors cursor-pointer"
                >
                  <IconClose className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}

        {!currentGroup || !currentPhoto ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-[#161618]">
            <IconPhotoStack className="w-12 h-12 text-[#48484A] mb-3" />
            <h3 className="text-[15px] font-semibold text-[#AEAEB2]">
              {t.results.emptySelectionTitle}
            </h3>
            <p className="text-[12.5px] text-[#636366] max-w-xs mt-1 leading-relaxed">
              {t.results.emptySelectionPrompt}
            </p>
          </div>
        ) : (
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden bg-[#141416]">
            {/* Clean Metadata & Score Header */}
            <div className="px-5 py-2.5 border-b border-white/[0.06] bg-[#1A1A1C] shrink-0 space-y-2">
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <h2
                      className="text-[15px] font-semibold tracking-tight text-[#F2F2F7] truncate"
                      title={currentGroup.title}
                    >
                      {currentGroup.title}
                    </h2>
                    {isCurrentPhotoBest && (
                      <span className="shrink-0 whitespace-nowrap inline-flex items-center gap-1.5 text-[11px] font-medium px-2 py-0.5 rounded-[6px] bg-[#30D158]/16 border border-[#30D158]/35 text-[#32D74B]">
                        {currentPhotoHasAesthetic ? (
                          <>
                            <IconSparkles className="w-3 h-3 shrink-0" />
                            <span>{t.results.bestPhotoBadge}</span>
                            {groupBestReasonText && (
                              <span className="text-[#32D74B]/85 font-normal">
                                ({groupBestReasonText})
                              </span>
                            )}
                          </>
                        ) : (
                          <>
                            <IconCheckCircle className="w-3 h-3 shrink-0" />
                            <span>{t.results.recommendedKeepBadge}</span>
                            {groupBestReasonKey === "largest_file" &&
                              groupBestReasonText && (
                                <span className="text-[#32D74B]/85 font-normal">
                                  ({groupBestReasonText})
                                </span>
                              )}
                          </>
                        )}
                      </span>
                    )}
                  </div>
                  <p
                    className="text-[12px] text-[#8E8E93] truncate mt-0.5"
                    title={currentPhoto.file_path}
                  >
                    {currentPhoto.file_path}
                    {currentPhoto.width && currentPhoto.height
                      ? ` • ${currentPhoto.width}×${currentPhoto.height}`
                      : ""}{" "}
                    •{" "}
                    <span className="text-[#E5E5EA] font-medium whitespace-nowrap tabular-nums">
                      {formatBytes(currentPhoto.file_size)}
                    </span>
                  </p>
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xl font-medium text-[#0A84FF] tabular-nums">
                      {selectedInCurrentGroup}
                    </span>
                    <span className="text-[11px] leading-tight text-[#8E8E93] whitespace-nowrap">
                      {t.results.statSelectedLine1}
                      <br />
                      {t.results.statSelectedLine2}
                    </span>
                  </div>

                  <div className="h-5 w-px bg-white/[0.10]" />

                  <div className="flex items-center gap-1.5">
                    <span className="text-xl font-medium text-[#F2F2F7] tabular-nums">
                      {currentGroup.photos.length}
                    </span>
                    <span className="text-[11px] leading-tight text-[#8E8E93] whitespace-nowrap">
                      {t.results.statTotalLine1}
                      <br />
                      {t.results.statTotalLine2}
                    </span>
                  </div>
                </div>
              </div>

              {/* Aesthetic & Technical Score Pills (Strictly Scored Similars Only) */}
              {currentPhotoHasAesthetic && (
                <div className="space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2 text-[11px]">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border font-medium tabular-nums ${getAestheticScoreToneClasses(
                        currentPhoto.aesthetic_score
                      )}`}
                    >
                      <IconSparkles className="w-3 h-3 shrink-0" />
                      <span>{t.results.aestheticScoreLabel}:</span>
                      <span>
                        {formatQualityScore(currentPhoto.aesthetic_score, lang)}{" "}
                        / 100
                      </span>
                    </span>

                    {currentPhoto.quality_score !== null && (
                      <span
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[#252528] border border-white/[0.08] text-[#E5E5EA] font-medium tabular-nums"
                        title={`${t.results.metricSharpness}: ${formatQualityScore(
                          currentPhoto.sharpness_score,
                          lang,
                          0
                        )} • ${t.results.metricExposure}: ${formatQualityScore(
                          currentPhoto.exposure_score,
                          lang,
                          0
                        )} • ${t.results.metricContrast}: ${formatQualityScore(
                          currentPhoto.contrast_score,
                          lang,
                          0
                        )}`}
                      >
                        <span className="text-[#8E8E93]">
                          {t.results.techScoreShortLabel}:
                        </span>
                        <b className="text-white font-semibold">
                          {formatQualityScore(currentPhoto.quality_score, lang)}
                        </b>
                      </span>
                    )}

                    {getAestheticMetricItems(currentPhoto).map((m) => (
                      <div
                        key={m.key}
                        className="inline-flex items-center gap-2 px-2 py-0.5 rounded-md bg-[#252528] border border-white/[0.08] text-[#E5E5EA] tabular-nums"
                      >
                        <span className="text-[#AEAEB2]">{m.label}</span>
                        <div className="w-11 h-1.5 rounded-full bg-white/[0.10] overflow-hidden">
                          <div
                            className={`h-full ${m.barClass} rounded-full`}
                            style={{
                              width: `${Math.min(
                                100,
                                Math.round(m.value ?? 0)
                              )}%`,
                            }}
                          />
                        </div>
                        <b className="font-semibold text-white">
                          {formatQualityScore(m.value, lang, 0)}
                        </b>
                      </div>
                    ))}

                    {currentPhoto.sharpness_score !== null && (
                      <div className="inline-flex items-center gap-2 px-2 py-0.5 rounded-md bg-[#252528] border border-white/[0.08] text-[#E5E5EA] tabular-nums">
                        <span className="text-[#AEAEB2]">
                          {t.results.metricSharpness}
                        </span>
                        <div className="w-11 h-1.5 rounded-full bg-white/[0.10] overflow-hidden">
                          <div
                            className="h-full bg-[#0A84FF] rounded-full"
                            style={{
                              width: `${Math.min(
                                100,
                                Math.round(currentPhoto.sharpness_score ?? 0)
                              )}%`,
                            }}
                          />
                        </div>
                        <b className="font-semibold text-white">
                          {formatQualityScore(
                            currentPhoto.sharpness_score,
                            lang,
                            0
                          )}
                        </b>
                      </div>
                    )}
                  </div>

                  {renderAestheticTagPills(currentPhoto, false)}
                </div>
              )}
            </div>

            {viewLayout === "single" ? (
              <div className="flex-1 flex flex-col min-h-0 overflow-hidden p-4 bg-[#141416]">
                {/* Neutral Darkroom Photo Stage */}
                <div className="relative flex-1 min-h-0 bg-[#1A1A1C] border border-white/[0.07] rounded-xl overflow-hidden flex items-center justify-center p-2.5">
                  <img
                    src={`${currentPhoto.thumbnail_url}?size=1200`}
                    alt={currentPhoto.file_name}
                    className="max-h-full max-w-full object-contain rounded-md"
                  />

                  {/* Top-left Selection Badge */}
                  <div
                    onClick={() => toggleSelectPhoto(currentPhoto.id)}
                    className={`whitespace-nowrap absolute top-3 left-3 flex items-center gap-2 px-3 py-1.5 rounded-[8px] text-[12px] font-medium cursor-pointer transition-colors border ${
                      selectedPhotoIds.has(currentPhoto.id)
                        ? "bg-[#007AFF]/22 border-[#0A84FF]/70 text-white backdrop-blur-md"
                        : "bg-[#242426]/90 hover:bg-[#2C2C2E] border-white/[0.12] text-[#F2F2F7] backdrop-blur-md"
                    }`}
                  >
                    <CustomCheckbox
                      size="sm"
                      checked={selectedPhotoIds.has(currentPhoto.id)}
                      onChange={(e) => toggleSelectPhoto(currentPhoto.id, e)}
                    />
                    <span>
                      {selectedPhotoIds.has(currentPhoto.id)
                        ? t.results.statusSelectedToDelete
                        : t.results.statusKeepingClickToDelete}
                    </span>
                  </div>

                  {/* Top-right Aesthetic Score Badge (Scored Similars Only) */}
                  {currentPhotoHasAesthetic && (
                    <div
                      className={`whitespace-nowrap absolute top-3 right-3 flex items-center gap-2 px-3 py-1.5 rounded-[8px] text-[12px] font-medium backdrop-blur-md border tabular-nums ${getAestheticScoreToneClasses(
                        currentPhoto.aesthetic_score
                      )}`}
                    >
                      <span className="inline-flex items-center gap-1">
                        <IconSparkles className="w-3.5 h-3.5" />
                        <span>
                          {formatQualityScore(currentPhoto.aesthetic_score, lang)}
                        </span>
                        <span className="opacity-75 font-normal">/ 100</span>
                      </span>
                      {currentPhoto.quality_score !== null && (
                        <>
                          <span className="opacity-30">|</span>
                          <span className="text-[11px] text-[#E5E5EA] font-normal">
                            {t.results.techScoreShortLabel}{" "}
                            {formatQualityScore(currentPhoto.quality_score, lang)}
                          </span>
                        </>
                      )}
                    </div>
                  )}
                </div>

                {/* Crisp macOS Filmstrip */}
                <div className="mt-3 shrink-0 flex items-center justify-start lg:justify-center gap-2 overflow-x-auto py-0.5">
                  {currentGroup.photos.map((p, idx) => {
                    const isChecked = selectedPhotoIds.has(p.id);
                    const isActive = currentPhoto.id === p.id;
                    const isBest = p.is_best || idx === 0;
                    const pHasAesthetic = isSimPhotoScored(
                      currentGroup.kind,
                      p
                    );
                    return (
                      <div
                        key={p.id}
                        onClick={() => setActivePhotoId(p.id)}
                        className={`shrink-0 flex items-center gap-2.5 p-2 rounded-xl cursor-pointer transition-colors border ${
                          isActive
                            ? "bg-[#2C2C2E] border-[#0A84FF]/70"
                            : isChecked
                            ? "bg-[#1E1E20] border-[#0A84FF]/45 hover:bg-[#252528]"
                            : isBest
                            ? "bg-[#1E1E20] border-[#30D158]/45 hover:bg-[#252528]"
                            : "bg-[#1E1E20] border-white/[0.08] hover:bg-[#252528]"
                        }`}
                      >
                        <CustomCheckbox
                          checked={isChecked}
                          onChange={(e) => toggleSelectPhoto(p.id, e)}
                        />
                        <img
                          src={p.thumbnail_url}
                          alt={p.file_name}
                          className="w-11 h-11 rounded-lg object-cover bg-[#141416] shrink-0 border border-white/[0.08]"
                        />
                        <div className="pr-1.5 text-left min-w-0">
                          <div className="flex items-center gap-1.5">
                            <p className="text-[12px] font-medium text-[#F2F2F7] truncate max-w-[125px]">
                              {p.file_name}
                            </p>
                            {pHasAesthetic && (
                              <span
                                className={`text-[10px] font-medium tabular-nums px-1.5 py-0.5 rounded-[5px] border ${getAestheticScoreToneClasses(
                                  p.aesthetic_score
                                )}`}
                              >
                                ✦ {formatQualityScore(p.aesthetic_score, lang)}
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-[#8E8E93] whitespace-nowrap mt-0.5 tabular-nums">
                            {formatBytes(p.file_size)}
                            {pHasAesthetic && p.quality_score !== null && (
                              <span className="text-[#AEAEB2]">
                                {" "}
                                • {t.results.techScoreShortLabel}{" "}
                                {formatQualityScore(p.quality_score, lang)}
                              </span>
                            )}{" "}
                            {isBest && (
                              <span className="text-[#32D74B] font-medium">
                                {t.results.filmstripSuggestedKeep}
                              </span>
                            )}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto p-4 bg-[#141416] grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-3.5 content-start">
                {currentGroup.photos.map((photo, index) => {
                  const isChecked = selectedPhotoIds.has(photo.id);
                  const isBest = photo.is_best || index === 0;
                  const cardHasAesthetic = isSimPhotoScored(
                    currentGroup.kind,
                    photo
                  );
                  const aestheticMetrics = cardHasAesthetic
                    ? getAestheticMetricItems(photo)
                    : [];
                  const aestheticColsCls =
                    aestheticMetrics.length >= 2
                      ? "grid-cols-2"
                      : "grid-cols-1";

                  return (
                    <div
                      key={photo.id}
                      onClick={() => setActivePhotoId(photo.id)}
                      className={`rounded-xl p-3.5 flex flex-col justify-between cursor-pointer transition-colors bg-[#1E1E20] border ${
                        isChecked
                          ? "border-[#0A84FF]/70 ring-1 ring-[#0A84FF]/25"
                          : isBest
                          ? "border-[#30D158]/60"
                          : "border-white/[0.08] hover:border-white/[0.16]"
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2 mb-2.5">
                          <div
                            onClick={(e) => toggleSelectPhoto(photo.id, e)}
                            className="flex items-center gap-2 text-[12px] font-medium cursor-pointer whitespace-nowrap min-w-0"
                          >
                            <CustomCheckbox
                              checked={isChecked}
                              onChange={(e) => toggleSelectPhoto(photo.id, e)}
                            />
                            <span
                              className={`truncate ${
                                isChecked
                                  ? "text-[#0A84FF]"
                                  : isBest
                                  ? "text-[#32D74B]"
                                  : "text-[#E5E5EA]"
                              }`}
                            >
                              {isChecked
                                ? t.results.statusSelectedToDelete
                                : isBest
                                ? t.results.cardSuggestedKeep
                                : t.results.cardPhotoIndex(index + 1)}
                            </span>
                          </div>

                          {cardHasAesthetic ? (
                            <div className="flex items-center gap-1 shrink-0 tabular-nums">
                              <span
                                className={`text-[11px] font-medium px-2 py-0.5 rounded-[5px] border whitespace-nowrap ${getAestheticScoreToneClasses(
                                  photo.aesthetic_score
                                )}`}
                              >
                                ✦{" "}
                                {formatQualityScore(
                                  photo.aesthetic_score,
                                  lang
                                )}
                              </span>
                              {photo.quality_score !== null && (
                                <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-[5px] bg-[#252528] border border-white/[0.08] text-[#AEAEB2] whitespace-nowrap">
                                  {t.results.techScoreShortLabel}{" "}
                                  {formatQualityScore(
                                    photo.quality_score,
                                    lang
                                  )}
                                </span>
                              )}
                            </div>
                          ) : (
                            <span className="text-[11.5px] text-[#8E8E93] whitespace-nowrap shrink-0 tabular-nums">
                              {formatBytes(photo.file_size)}
                            </span>
                          )}
                        </div>

                        <div
                          onDoubleClick={() =>
                            openPhotoOnMacApi(photo.id, "preview")
                          }
                          className="relative w-full h-52 bg-[#141416] border border-white/[0.06] rounded-lg overflow-hidden flex items-center justify-center p-1.5"
                        >
                          <img
                            src={`${photo.thumbnail_url}?size=720`}
                            alt={photo.file_name}
                            className="max-h-full max-w-full object-contain rounded"
                          />
                          {isBest && (
                            <span className="absolute bottom-2 left-2 inline-flex items-center gap-1 text-[10.5px] font-medium px-2 py-0.5 rounded-[6px] bg-[#1C1C1E]/90 backdrop-blur-md border border-[#30D158]/40 text-[#32D74B]">
                              {cardHasAesthetic ? (
                                <>
                                  <IconSparkles className="w-3 h-3 shrink-0" />
                                  <span>{groupBestReasonText}</span>
                                </>
                              ) : (
                                <>
                                  <IconCheckCircle className="w-3 h-3 shrink-0" />
                                  <span>
                                    {groupBestReasonKey === "largest_file"
                                      ? groupBestReasonText
                                      : t.results.recommendedKeepBadge}
                                  </span>
                                </>
                              )}
                            </span>
                          )}
                        </div>

                        <div className="mt-2.5 text-[12px] space-y-1.5 min-w-0">
                          <div className="flex items-center justify-between gap-2">
                            <p className="font-medium text-[#F2F2F7] truncate">
                              {photo.file_name}
                            </p>
                            <span className="text-[11px] text-[#8E8E93] whitespace-nowrap shrink-0 tabular-nums">
                              {photo.width && photo.height
                                ? `${photo.width}×${photo.height} • `
                                : ""}
                              {formatBytes(photo.file_size)}
                            </span>
                          </div>

                          <p className="text-[#8E8E93] text-[11px] truncate">
                            {t.results.cardFolderPrefix} {photo.folder_name}
                          </p>

                          {cardHasAesthetic && (
                            <>
                              {renderAestheticTagPills(photo, true)}

                              {aestheticMetrics.length > 0 && (
                                <div
                                  className={`grid ${aestheticColsCls} gap-1.5 pt-1 text-[10px] tabular-nums`}
                                >
                                  {aestheticMetrics.map((m) => (
                                    <div
                                      key={m.key}
                                      className="bg-[#252528] border border-white/[0.07] rounded-md px-2 py-1"
                                    >
                                      <div className="flex items-center justify-between gap-1 text-[#AEAEB2] mb-0.5">
                                        <span className="truncate">
                                          {m.label}
                                        </span>
                                        <b className="text-white shrink-0">
                                          {formatQualityScore(
                                            m.value,
                                            lang,
                                            0
                                          )}
                                        </b>
                                      </div>
                                      <div className="w-full h-1 bg-white/[0.10] rounded-full overflow-hidden">
                                        <div
                                          className={`h-full ${m.barClass} rounded-full`}
                                          style={{
                                            width: `${Math.min(
                                              100,
                                              Math.round(m.value ?? 0)
                                            )}%`,
                                          }}
                                        />
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}

                              {photo.sharpness_score !== null && (
                                <div className="grid grid-cols-3 gap-1.5 pt-1 text-[10px] tabular-nums">
                                  <div className="bg-[#18181A] border border-white/[0.06] rounded-md px-2 py-1">
                                    <div className="flex items-center justify-between text-[#8E8E93] mb-0.5">
                                      <span className="truncate">
                                        {t.results.metricSharpness}
                                      </span>
                                      <b className="text-white">
                                        {formatQualityScore(
                                          photo.sharpness_score,
                                          lang,
                                          0
                                        )}
                                      </b>
                                    </div>
                                    <div className="w-full h-1 bg-white/[0.10] rounded-full overflow-hidden">
                                      <div
                                        className="h-full bg-[#0A84FF] rounded-full"
                                        style={{
                                          width: `${Math.min(
                                            100,
                                            Math.round(
                                              photo.sharpness_score ?? 0
                                            )
                                          )}%`,
                                        }}
                                      />
                                    </div>
                                  </div>

                                  <div className="bg-[#18181A] border border-white/[0.06] rounded-md px-2 py-1">
                                    <div className="flex items-center justify-between text-[#8E8E93] mb-0.5">
                                      <span className="truncate">
                                        {t.results.metricExposure}
                                      </span>
                                      <b className="text-white">
                                        {formatQualityScore(
                                          photo.exposure_score,
                                          lang,
                                          0
                                        )}
                                      </b>
                                    </div>
                                    <div className="w-full h-1 bg-white/[0.10] rounded-full overflow-hidden">
                                      <div
                                        className="h-full bg-[#FFD60A] rounded-full"
                                        style={{
                                          width: `${Math.min(
                                            100,
                                            Math.round(
                                              photo.exposure_score ?? 0
                                            )
                                          )}%`,
                                        }}
                                      />
                                    </div>
                                  </div>

                                  <div className="bg-[#18181A] border border-white/[0.06] rounded-md px-2 py-1">
                                    <div className="flex items-center justify-between text-[#8E8E93] mb-0.5">
                                      <span className="truncate">
                                        {t.results.metricContrast}
                                      </span>
                                      <b className="text-white">
                                        {formatQualityScore(
                                          photo.contrast_score,
                                          lang,
                                          0
                                        )}
                                      </b>
                                    </div>
                                    <div className="w-full h-1 bg-white/[0.10] rounded-full overflow-hidden">
                                      <div
                                        className="h-full bg-[#30D158] rounded-full"
                                        style={{
                                          width: `${Math.min(
                                            100,
                                            Math.round(
                                              photo.contrast_score ?? 0
                                            )
                                          )}%`,
                                        }}
                                      />
                                    </div>
                                  </div>
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Slim Native macOS Bottom Action Bar */}
        <footer className="h-11 bg-[#1C1C1E] border-t border-white/[0.07] px-4 flex items-center justify-between gap-3 shrink-0 text-[12px]">
          <div className="text-[#8E8E93] truncate tabular-nums">
            {t.results.footerFoundPrefix}{" "}
            <b className="text-[#E5E5EA] font-medium">
              {formatBytes(totalAllBytes)}
            </b>{" "}
            {t.results.footerInMiddle}{" "}
            <b className="text-[#E5E5EA] font-medium">
              {serverTotalFilesCount}
            </b>{" "}
            {t.results.footerPhotosSuffix(serverTotalFilesCount)}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {currentPhoto && (
              <button
                type="button"
                onClick={() => openPhotoOnMacApi(currentPhoto.id, "finder")}
                className="whitespace-nowrap bg-[#2C2C2E] hover:bg-[#3A3A3C] text-[#E5E5EA] hover:text-white px-3 py-1 rounded-[7px] font-medium inline-flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <IconFinder className="w-[14px] h-[14px] text-[#AEAEB2]" />
                <span>{t.results.btnShowInFinder}</span>
              </button>
            )}

            <button
              type="button"
              onClick={onSmartCleanup}
              disabled={isCleaning}
              title={t.results.btnFreeUpTooltip}
              className={`whitespace-nowrap font-medium px-3.5 py-1 rounded-[7px] inline-flex items-center gap-1.5 transition-colors cursor-pointer disabled:bg-[#2C2C2E] disabled:text-[#636366] ${
                selectedPhotoIds.size === 0
                  ? "bg-[#2C2C2E] hover:bg-[#3A3A3C] text-[#98989D]"
                  : "bg-[#007AFF] hover:bg-[#0071EB] text-white shadow-xs"
              }`}
            >
              <IconTrash className="w-[14px] h-[14px]" />
              <span>
                {isCleaning
                  ? t.results.btnCleaning
                  : t.results.btnFreeUp(formatBytes(totalSelectedBytes))}
              </span>
            </button>
          </div>
        </footer>
      </main>
    </div>
  );
}
