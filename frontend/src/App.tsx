import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import "./App.css";
import {
  ClusterGroup,
  DuplicateGroup,
  ScanProgressState,
  checkBackendHealthApi,
  fetchScanProgressApi,
  cancelScanApi,
  scanDirectoryApi,
  clusterPhotosApi,
  scoreClusterAestheticsApi,
  fetchClustersApi,
  fetchDuplicatesApi,
  deleteMultiplePhotosApi,
  resetDatabaseApi,
} from "./api/PhotoApi";
import {
  ScanStepKey,
  ScreenMode,
  SidebarFilter,
  UnifiedGroup,
  getBaseTitle,
} from "./utils/photoHelpers";
import { useI18n } from "./i18n/I18nContext";
import LanguageSwitcher from "./components/LanguageSwitcher";
import GlassModal from "./components/GlassModal";
import GlassToast, { ToastTone } from "./components/GlassToast";
import { IconWarning } from "./components/MacIcons";
import HomePage from "./pages/HomePage";
import ScanningPage from "./pages/ScanningPage";
import ResultsPage from "./pages/ResultsPage";

const PAGE_SIZE = 100;

type ToastState =
  | { id: number; tone: "success"; kind: "trashed"; count: number; bytes: number }
  | { id: number; tone: "success"; kind: "aesthetic"; count: number }
  | { id: number; tone: "warning"; kind: "no_selection" }
  | { id: number; tone: "warning"; kind: "cancelled" }
  | {
      id: number;
      tone: ToastTone;
      kind: "custom";
      fallbackKey: "errScan" | "errCluster" | "errAesthetic" | "errCleanup";
      customMessage?: string;
    };

function resolveDroppedFolderPath(rawPath: string): string {
  const trimmed = rawPath.replace(/\/+$/, "");
  if (!trimmed) return rawPath;
  if (/\.(jpe?g|png|heic|heif)$/i.test(trimmed)) {
    const lastSlash = Math.max(
      trimmed.lastIndexOf("/"),
      trimmed.lastIndexOf("\\")
    );
    if (lastSlash > 0) {
      return trimmed.slice(0, lastSlash);
    }
    if (lastSlash === 0) {
      return "/";
    }
  }
  return trimmed;
}

export default function App() {
  const { t, formatBytes } = useI18n();

  const [screen, setScreen] = useState<ScreenMode>("home");
  const [backendReady, setBackendReady] = useState<boolean>(false);
  const [isBootingBackend, setIsBootingBackend] = useState<boolean>(false);
  const [bootTimedOut, setBootTimedOut] = useState<boolean>(false);
  const [bootAttempt, setBootAttempt] = useState<number>(0);

  const [folderPath, setFolderPath] = useState<string>("");
  const [isDraggingFolder, setIsDraggingFolder] = useState<boolean>(false);
  const [runAiClusterToo, setRunAiClusterToo] = useState<boolean>(true);
  const [clearOldDataBeforeScan, setClearOldDataBeforeScan] =
    useState<boolean>(true);

  const [scanStep, setScanStep] = useState<ScanStepKey>("idle");
  const [progress, setProgress] = useState<ScanProgressState>({
    phase: "idle",
    current: 0,
    total: 0,
    percent: 0,
    current_file: "",
    new_added: 0,
    exact_duplicates: 0,
    already_indexed: 0,
  });

  const cancelRef = useRef<boolean>(false);
  const [isCancelling, setIsCancelling] = useState<boolean>(false);

  const [dupGroups, setDupGroups] = useState<DuplicateGroup[]>([]);
  const [clusters, setClusters] = useState<ClusterGroup[]>([]);

  const [totalDupGroups, setTotalDupGroups] = useState<number>(0);
  const [totalDupBytes, setTotalDupBytes] = useState<number | undefined>(
    undefined
  );
  const [totalDupPhotos, setTotalDupPhotos] = useState<number | undefined>(
    undefined
  );

  const [totalSimGroups, setTotalSimGroups] = useState<number>(0);
  const [totalSimBytes, setTotalSimBytes] = useState<number | undefined>(
    undefined
  );
  const [totalSimPhotos, setTotalSimPhotos] = useState<number | undefined>(
    undefined
  );

  const [disconnectedVolumes, setDisconnectedVolumes] = useState<string[]>([]);

  const loadingMoreDupsRef = useRef<boolean>(false);
  const [isLoadingMoreDups, setIsLoadingMoreDups] = useState<boolean>(false);
  const loadingMoreSimsRef = useRef<boolean>(false);
  const [isLoadingMoreSims, setIsLoadingMoreSims] = useState<boolean>(false);

  const [sidebarFilter, setSidebarFilter] =
    useState<SidebarFilter>("duplicates");
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>(
    {}
  );
  const [selectedPhotoIds, setSelectedPhotoIds] = useState<Set<number>>(
    new Set()
  );
  const [isCleaning, setIsCleaning] = useState<boolean>(false);
  const [cleanupConfirm, setCleanupConfirm] = useState<{
    ids: number[];
    selectedBytes: number;
  } | null>(null);

  const toastSeqRef = useRef<number>(0);
  const [toast, setToast] = useState<ToastState | null>(null);

  const dismissToast = useCallback(() => {
    setToast(null);
  }, []);

  const showErrorToast = useCallback(
    (
      fallbackKey: "errScan" | "errCluster" | "errAesthetic" | "errCleanup",
      err?: unknown
    ) => {
      const msg =
        err instanceof Error && err.message ? err.message : undefined;
      toastSeqRef.current += 1;
      setToast({
        id: toastSeqRef.current,
        tone: "error",
        kind: "custom",
        fallbackKey,
        customMessage: msg,
      });
    },
    []
  );

  const toastMessage = useMemo(() => {
    if (!toast) return "";
    switch (toast.kind) {
      case "trashed":
        return t.app.toastTrashedSuccess(
          toast.count,
          formatBytes(toast.bytes)
        );
      case "aesthetic":
        return t.app.toastAestheticSuccess(toast.count);
      case "no_selection":
        return t.app.alertNoSelection;
      case "cancelled":
        return t.app.toastCancelled;
      case "custom":
        return toast.customMessage || t.app[toast.fallbackKey];
    }
  }, [toast, t, formatBytes]);

  const showCancelledToast = useCallback(() => {
    toastSeqRef.current += 1;
    setToast({
      id: toastSeqRef.current,
      tone: "warning",
      kind: "cancelled",
    });
  }, []);

  const scanPhaseText = useMemo(() => {
    switch (scanStep) {
      case "resetting":
        return t.app.phaseResetting;
      case "scanning_dups":
        return t.app.phaseScanningDups;
      case "clustering_ai":
        return t.app.phaseClusteringAi;
      case "scoring_aesthetics":
        return t.app.phaseScoringAesthetics;
      default:
        return "";
    }
  }, [scanStep, t]);

  const loadData = useCallback(
    async (
      autoSelectDuplicates = false
    ): Promise<{
      dupCount: number;
      simCount: number;
      disconnectedCount: number;
    }> => {
      try {
        const [clusterRes, dupRes] = await Promise.all([
          fetchClustersApi(PAGE_SIZE, 0),
          fetchDuplicatesApi(PAGE_SIZE, 0),
        ]);
        setClusters(clusterRes.items);
        setDupGroups(dupRes.items);

        const nextSimTotal =
          clusterRes.total_clusters ?? clusterRes.items.length;
        setTotalSimGroups(nextSimTotal);
        setTotalSimBytes(clusterRes.total_bytes);
        setTotalSimPhotos(clusterRes.total_photos);

        const nextDupTotal = dupRes.total_groups ?? dupRes.items.length;
        setTotalDupGroups(nextDupTotal);
        setTotalDupBytes(dupRes.total_bytes);
        setTotalDupPhotos(dupRes.total_photos);

        const mergedVolumes = Array.from(
          new Set([
            ...(dupRes.disconnected_volumes ?? []),
            ...(clusterRes.disconnected_volumes ?? []),
          ])
        ).sort();
        setDisconnectedVolumes(mergedVolumes);

        if (autoSelectDuplicates) {
          const autoIds = new Set<number>();
          const initialExpanded: Record<string, boolean> = {};
          dupRes.items.forEach((g, idx) => {
            const gKey = `dup-${g.phash}`;
            if (idx < 3) initialExpanded[gKey] = true;
            g.photos.forEach((p, pIdx) => {
              const isBest = p.is_best || pIdx === 0;
              if (!isBest) {
                autoIds.add(p.id);
              }
            });
          });
          clusterRes.items.slice(0, 2).forEach((c) => {
            initialExpanded[`sim-${c.cluster_id}`] = true;
          });
          setSelectedPhotoIds(autoIds);
          setExpandedGroups(initialExpanded);
        }

        return {
          dupCount: nextDupTotal,
          simCount: nextSimTotal,
          disconnectedCount: mergedVolumes.length,
        };
      } catch {
        // Bỏ qua nếu server chưa bật ở màn hình Home
        return { dupCount: 0, simCount: 0, disconnectedCount: 0 };
      }
    },
    []
  );

  const loadMoreDuplicates = useCallback(async () => {
    if (loadingMoreDupsRef.current || dupGroups.length >= totalDupGroups) {
      return;
    }
    loadingMoreDupsRef.current = true;
    setIsLoadingMoreDups(true);
    try {
      const res = await fetchDuplicatesApi(PAGE_SIZE, dupGroups.length);
      if (res.total_bytes !== undefined) setTotalDupBytes(res.total_bytes);
      if (res.total_photos !== undefined) setTotalDupPhotos(res.total_photos);
      if (res.disconnected_volumes) {
        setDisconnectedVolumes((prev) =>
          Array.from(
            new Set([...prev, ...(res.disconnected_volumes ?? [])])
          ).sort()
        );
      }
      if (res.items.length === 0) {
        setTotalDupGroups(dupGroups.length);
      } else if (res.total_groups !== undefined) {
        setTotalDupGroups(res.total_groups);
      }
      setDupGroups((prev) => {
        const seen = new Set(prev.map((g) => g.phash));
        const appended = res.items.filter((g) => !seen.has(g.phash));
        return appended.length > 0 ? [...prev, ...appended] : prev;
      });
    } catch (err) {
      showErrorToast("errScan", err);
    } finally {
      loadingMoreDupsRef.current = false;
      setIsLoadingMoreDups(false);
    }
  }, [dupGroups.length, totalDupGroups, showErrorToast]);

  const loadMoreClusters = useCallback(async () => {
    if (loadingMoreSimsRef.current || clusters.length >= totalSimGroups) {
      return;
    }
    loadingMoreSimsRef.current = true;
    setIsLoadingMoreSims(true);
    try {
      const res = await fetchClustersApi(PAGE_SIZE, clusters.length);
      if (res.total_bytes !== undefined) setTotalSimBytes(res.total_bytes);
      if (res.total_photos !== undefined) setTotalSimPhotos(res.total_photos);
      if (res.disconnected_volumes) {
        setDisconnectedVolumes((prev) =>
          Array.from(
            new Set([...prev, ...(res.disconnected_volumes ?? [])])
          ).sort()
        );
      }
      if (res.items.length === 0) {
        setTotalSimGroups(clusters.length);
      } else if (res.total_clusters !== undefined) {
        setTotalSimGroups(res.total_clusters);
      }
      setClusters((prev) => {
        const seen = new Set(prev.map((c) => c.cluster_id));
        const appended = res.items.filter((c) => !seen.has(c.cluster_id));
        return appended.length > 0 ? [...prev, ...appended] : prev;
      });
    } catch (err) {
      showErrorToast("errCluster", err);
    } finally {
      loadingMoreSimsRef.current = false;
      setIsLoadingMoreSims(false);
    }
  }, [clusters.length, totalSimGroups, showErrorToast]);

  const handleRetryBackendConnect = useCallback(() => {
    setBootTimedOut(false);
    setIsBootingBackend(true);
    setBootAttempt((prev) => prev + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    let pollTimer: number | undefined;

    const verifyBackend = async () => {
      const immediateOk = await checkBackendHealthApi();
      if (cancelled) return;
      if (immediateOk) {
        setBackendReady(true);
        setBootTimedOut(false);
        setIsBootingBackend(false);
        void loadData(true);
        return;
      }

      setIsBootingBackend(true);
      setBootTimedOut(false);
      const startedAt = Date.now();
      const maxWaitMs = 25_000;

      const pollOnce = async () => {
        if (cancelled) return;
        const ok = await checkBackendHealthApi();
        if (cancelled) return;
        if (ok) {
          setBackendReady(true);
          setBootTimedOut(false);
          setIsBootingBackend(false);
          void loadData(true);
          return;
        }
        if (Date.now() - startedAt >= maxWaitMs) {
          setBootTimedOut(true);
          return;
        }
        pollTimer = window.setTimeout(() => {
          void pollOnce();
        }, 350);
      };

      pollTimer = window.setTimeout(() => {
        void pollOnce();
      }, 350);
    };

    void verifyBackend();

    return () => {
      cancelled = true;
      if (pollTimer !== undefined) {
        window.clearTimeout(pollTimer);
      }
    };
  }, [bootAttempt, loadData]);

  // Lắng nghe kéo-thả thư mục / tệp ảnh từ Finder qua Tauri v2 Webview
  useEffect(() => {
    if (screen !== "home" || isBootingBackend) {
      setIsDraggingFolder(false);
      return;
    }

    let cancelled = false;
    let unlistenFn: (() => void) | undefined;

    try {
      getCurrentWebview()
        .onDragDropEvent((event) => {
          if (cancelled) return;
          const payload = event.payload;
          if (payload.type === "enter" || payload.type === "over") {
            setIsDraggingFolder(true);
          } else if (payload.type === "leave") {
            setIsDraggingFolder(false);
          } else if (payload.type === "drop") {
            setIsDraggingFolder(false);
            const firstPath = payload.paths?.[0];
            if (firstPath) {
              setFolderPath(resolveDroppedFolderPath(firstPath));
            }
          }
        })
        .then((unlisten) => {
          if (cancelled) {
            unlisten();
          } else {
            unlistenFn = unlisten;
          }
        })
        .catch(() => {
          // Bỏ qua khi chạy trên trình duyệt thường ngoài Tauri runtime
        });
    } catch {
      // Bỏ qua khi chạy trên trình duyệt thường ngoài Tauri runtime
    }

    return () => {
      cancelled = true;
      if (unlistenFn) {
        unlistenFn();
      }
    };
  }, [screen, isBootingBackend]);

  // Tự động đồng bộ lại với ổ cứng mỗi khi người dùng từ Finder chuyển về lại cửa sổ App
  useEffect(() => {
    const handleWindowFocus = () => {
      if (screen === "results" && backendReady) {
        loadData(false);
      }
    };
    window.addEventListener("focus", handleWindowFocus);
    return () => window.removeEventListener("focus", handleWindowFocus);
  }, [screen, backendReady, loadData]);

  // Lắng nghe tiến độ quét / gom nhóm theo thời gian thực
  useEffect(() => {
    if (screen !== "scanning") return;

    const timer = window.setInterval(async () => {
      try {
        const p = await fetchScanProgressApi();
        setProgress(p);
      } catch {
        // Bỏ qua lỗi mạng tạm thời
      }
    }, 250);

    return () => window.clearInterval(timer);
  }, [screen]);

  const unifiedDupGroups: UnifiedGroup[] = useMemo(() => {
    return dupGroups.map((g) => {
      const firstPhoto = g.photos[0];
      const totalBytes = g.photos.reduce((sum, p) => sum + p.file_size, 0);
      return {
        key: `dup-${g.phash}`,
        kind: "duplicates",
        title: firstPhoto
          ? getBaseTitle(firstPhoto.file_name)
          : t.app.groupFallback(g.group_index),
        totalBytes,
        photos: g.photos,
      };
    });
  }, [dupGroups, t]);

  const unifiedSimGroups: UnifiedGroup[] = useMemo(() => {
    return clusters.map((c) => {
      const firstPhoto = c.photos[0];
      const totalBytes = c.photos.reduce((sum, p) => sum + p.file_size, 0);
      return {
        key: `sim-${c.cluster_id}`,
        kind: "similars",
        title: firstPhoto
          ? getBaseTitle(firstPhoto.file_name)
          : t.app.groupFallback(c.cluster_id),
        totalBytes,
        hasAestheticScores: Boolean(c.has_aesthetic_scores),
        photos: c.photos,
      };
    });
  }, [clusters, t]);

  const totalAllBytes = useMemo(() => {
    const loadedDupBytes = unifiedDupGroups.reduce(
      (s, g) => s + g.totalBytes,
      0
    );
    const loadedSimBytes = unifiedSimGroups.reduce(
      (s, g) => s + g.totalBytes,
      0
    );
    return (totalDupBytes || loadedDupBytes) + (totalSimBytes || loadedSimBytes);
  }, [unifiedDupGroups, unifiedSimGroups, totalDupBytes, totalSimBytes]);

  const handleCancelScan = useCallback(async () => {
    if (cancelRef.current) return;
    cancelRef.current = true;
    setIsCancelling(true);
    try {
      await cancelScanApi();
    } catch {
      // Bỏ qua nếu tác vụ vừa hoàn tất ngay thời điểm bấm dừng
    }
  }, []);

  const handlePickFolder = async () => {
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: t.app.dialogPickFolderTitle,
      });
      if (typeof selected === "string") {
        setFolderPath(selected);
      }
    } catch (err) {
      showErrorToast("errScan", err);
    }
  };

  const handleStartScan = async () => {
    if (!folderPath) {
      await handlePickFolder();
      return;
    }

    cancelRef.current = false;
    setIsCancelling(false);
    setProgress({
      phase: "scanning",
      current: 0,
      total: 0,
      percent: 0,
      current_file: "Đang chuẩn bị...",
      new_added: 0,
      exact_duplicates: 0,
      already_indexed: 0,
      cancel_requested: false,
    });
    setScreen("scanning");

    try {
      if (clearOldDataBeforeScan) {
        setScanStep("resetting");
        await resetDatabaseApi();
        if (cancelRef.current) {
          const counts = await loadData(true);
          showCancelledToast();
          const hasAny =
            counts.dupCount > 0 ||
            counts.simCount > 0 ||
            counts.disconnectedCount > 0;
          if (hasAny) {
            setSidebarFilter(counts.dupCount > 0 ? "duplicates" : "similars");
            setScreen("results");
          } else {
            setScreen("home");
          }
          return;
        }
      }

      setScanStep("scanning_dups");
      const scanRes = await scanDirectoryApi(folderPath);
      if (scanRes?.cancelled || cancelRef.current) {
        const counts = await loadData(true);
        showCancelledToast();
        const hasAny =
          counts.dupCount > 0 ||
          counts.simCount > 0 ||
          counts.disconnectedCount > 0;
        if (hasAny) {
          setSidebarFilter(counts.dupCount > 0 ? "duplicates" : "similars");
          setScreen("results");
        } else {
          setScreen("home");
        }
        return;
      }

      if (runAiClusterToo) {
        setScanStep("clustering_ai");
        const clusterRes = await clusterPhotosApi(0.85);
        if (clusterRes?.cancelled || cancelRef.current) {
          const counts = await loadData(true);
          showCancelledToast();
          const hasAny =
            counts.dupCount > 0 ||
            counts.simCount > 0 ||
            counts.disconnectedCount > 0;
          if (hasAny) {
            setSidebarFilter(counts.dupCount > 0 ? "duplicates" : "similars");
            setScreen("results");
          } else {
            setScreen("home");
          }
          return;
        }
      }

      await loadData(true);
      setSidebarFilter("duplicates");
      setScreen("results");
    } catch (err) {
      showErrorToast("errScan", err);
      setScreen("home");
    } finally {
      setScanStep("idle");
      cancelRef.current = false;
      setIsCancelling(false);
    }
  };

  const handleRunAiClusterFromResults = async () => {
    cancelRef.current = false;
    setIsCancelling(false);
    setProgress({
      phase: "clustering",
      current: 0,
      total: 0,
      percent: 0,
      current_file: "Đang chuẩn bị...",
      new_added: 0,
      exact_duplicates: 0,
      already_indexed: 0,
      cancel_requested: false,
    });
    setScreen("scanning");
    setScanStep("clustering_ai");
    try {
      const res = await clusterPhotosApi(0.85);
      await loadData(false);
      if (res?.cancelled || cancelRef.current) {
        showCancelledToast();
      } else {
        setSidebarFilter("similars");
      }
    } catch (err) {
      showErrorToast("errCluster", err);
    } finally {
      setScanStep("idle");
      cancelRef.current = false;
      setIsCancelling(false);
      setScreen("results");
    }
  };

  const handleRunAestheticScore = async () => {
    cancelRef.current = false;
    setIsCancelling(false);
    setProgress({
      phase: "aesthetic_scoring",
      current: 0,
      total: 0,
      percent: 0,
      current_file: "Đang chuẩn bị...",
      new_added: 0,
      exact_duplicates: 0,
      already_indexed: 0,
      cancel_requested: false,
    });
    setScreen("scanning");
    setScanStep("scoring_aesthetics");
    try {
      const res = await scoreClusterAestheticsApi();
      await loadData(false);
      setSidebarFilter("similars");
      if (res?.cancelled || cancelRef.current) {
        showCancelledToast();
      } else {
        toastSeqRef.current += 1;
        setToast({
          id: toastSeqRef.current,
          tone: "success",
          kind: "aesthetic",
          count: res.photos_scored,
        });
      }
    } catch (err) {
      showErrorToast("errAesthetic", err);
    } finally {
      setScanStep("idle");
      cancelRef.current = false;
      setIsCancelling(false);
      setScreen("results");
    }
  };

  const handleSmartCleanup = () => {
    const idsToDelete = Array.from(selectedPhotoIds);
    if (idsToDelete.length === 0) {
      toastSeqRef.current += 1;
      setToast({
        id: toastSeqRef.current,
        tone: "warning",
        kind: "no_selection",
      });
      return;
    }

    const photoMap = new Map<number, number>();
    unifiedDupGroups.forEach((g) =>
      g.photos.forEach((p) => photoMap.set(p.id, p.file_size))
    );
    unifiedSimGroups.forEach((g) =>
      g.photos.forEach((p) => photoMap.set(p.id, p.file_size))
    );
    let selectedBytes = 0;
    idsToDelete.forEach((id) => {
      selectedBytes += photoMap.get(id) || 0;
    });

    setCleanupConfirm({ ids: idsToDelete, selectedBytes });
  };

  const handleConfirmSmartCleanup = useCallback(async () => {
    if (!cleanupConfirm || isCleaning) return;
    const { ids, selectedBytes } = cleanupConfirm;

    setIsCleaning(true);
    try {
      const res = await deleteMultiplePhotosApi(ids);
      const deletedCount = res?.deleted_count ?? ids.length;
      const freedBytes = res?.freed_bytes ?? selectedBytes;

      setCleanupConfirm(null);
      setSelectedPhotoIds(new Set());
      await loadData(false);

      toastSeqRef.current += 1;
      setToast({
        id: toastSeqRef.current,
        tone: "success",
        kind: "trashed",
        count: deletedCount,
        bytes: freedBytes,
      });
    } catch (err) {
      setCleanupConfirm(null);
      showErrorToast("errCleanup", err);
    } finally {
      setIsCleaning(false);
    }
  }, [cleanupConfirm, isCleaning, loadData, showErrorToast]);

  const handleCancelSmartCleanup = useCallback(() => {
    if (!isCleaning) {
      setCleanupConfirm(null);
    }
  }, [isCleaning]);

  return (
    <>
      {isBootingBackend ? (
        <div className="h-screen w-screen bg-[#161618] text-[#F2F2F7] flex flex-col justify-between overflow-hidden select-none">
          <header
            data-tauri-drag-region
            className="h-[46px] pl-[80px] pr-4 bg-[#1C1C1E] border-b border-white/[0.07] flex items-center justify-between shrink-0"
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
            <div className="bg-[#1E1E20] border border-white/[0.08] rounded-2xl p-7 max-w-md w-full text-center shadow-xl flex flex-col items-center">
              <div className="relative w-14 h-14 rounded-2xl bg-[#252528] border border-white/[0.08] flex items-center justify-center mb-4">
                {!bootTimedOut ? (
                  <>
                    <img
                      src="/logo.png"
                      alt="UniPhoto"
                      className="w-8 h-8 rounded-lg object-contain"
                      onError={(e) => {
                        e.currentTarget.style.display = "none";
                      }}
                    />
                    <span className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-[#1E1E20] flex items-center justify-center">
                      <span className="w-3.5 h-3.5 rounded-full border-2 border-[#0A84FF] border-t-transparent animate-spin" />
                    </span>
                  </>
                ) : (
                  <IconWarning className="w-7 h-7 text-[#FFD60A]" />
                )}
              </div>

              <span
                className={`text-[11px] uppercase tracking-wider font-semibold ${
                  bootTimedOut ? "text-[#FFD60A]" : "text-[#0A84FF]"
                }`}
              >
                {bootTimedOut ? t.app.bootTimeoutBadge : t.app.bootingBadge}
              </span>

              <h1 className="text-[16px] font-semibold tracking-tight text-[#F2F2F7] mt-1.5 mb-2">
                {t.app.bootingTitle}
              </h1>

              <p className="text-[12.5px] text-[#8E8E93] leading-relaxed">
                {bootTimedOut ? t.app.bootTimeoutDesc : t.app.bootingSubtitle}
              </p>

              {bootTimedOut && (
                <button
                  type="button"
                  onClick={handleRetryBackendConnect}
                  className="mt-5 bg-[#007AFF] hover:bg-[#0071EB] px-6 py-2 rounded-[8px] font-medium text-[13px] text-white transition-colors cursor-pointer"
                >
                  {t.app.btnRetryConnect}
                </button>
              )}
            </div>
          </main>

          <div className="h-4 shrink-0" />
        </div>
      ) : screen === "home" ? (
        <HomePage
          folderPath={folderPath}
          isDraggingFolder={isDraggingFolder}
          onDragStateChange={setIsDraggingFolder}
          onDropPath={(rawPath) =>
            setFolderPath(resolveDroppedFolderPath(rawPath))
          }
          runAiClusterToo={runAiClusterToo}
          setRunAiClusterToo={setRunAiClusterToo}
          clearOldDataBeforeScan={clearOldDataBeforeScan}
          setClearOldDataBeforeScan={setClearOldDataBeforeScan}
          hasExistingResults={
            unifiedDupGroups.length > 0 ||
            unifiedSimGroups.length > 0 ||
            disconnectedVolumes.length > 0
          }
          totalAllBytes={totalAllBytes}
          onPickFolder={handlePickFolder}
          onStartScan={handleStartScan}
          onOpenResults={() => setScreen("results")}
        />
      ) : screen === "scanning" ? (
        <ScanningPage
          folderPath={folderPath}
          scanPhaseText={scanPhaseText}
          progress={progress}
          isCancelling={isCancelling || Boolean(progress.cancel_requested)}
          onCancelScan={handleCancelScan}
        />
      ) : (
        <ResultsPage
          unifiedDupGroups={unifiedDupGroups}
          unifiedSimGroups={unifiedSimGroups}
          totalDupGroups={totalDupGroups}
          totalDupBytes={totalDupBytes}
          totalDupPhotos={totalDupPhotos}
          totalSimGroups={totalSimGroups}
          totalSimBytes={totalSimBytes}
          totalSimPhotos={totalSimPhotos}
          hasMoreDups={dupGroups.length < totalDupGroups}
          hasMoreSims={clusters.length < totalSimGroups}
          isLoadingMoreDups={isLoadingMoreDups}
          isLoadingMoreSims={isLoadingMoreSims}
          onLoadMoreDups={loadMoreDuplicates}
          onLoadMoreSims={loadMoreClusters}
          disconnectedVolumes={disconnectedVolumes}
          selectedPhotoIds={selectedPhotoIds}
          setSelectedPhotoIds={setSelectedPhotoIds}
          expandedGroups={expandedGroups}
          setExpandedGroups={setExpandedGroups}
          sidebarFilter={sidebarFilter}
          setSidebarFilter={setSidebarFilter}
          isCleaning={isCleaning}
          isModalOpen={cleanupConfirm !== null}
          onBackHome={() => setScreen("home")}
          onRefresh={() => loadData(false)}
          onRunAiCluster={handleRunAiClusterFromResults}
          onRunAestheticScore={handleRunAestheticScore}
          onSmartCleanup={handleSmartCleanup}
        />
      )}

      <GlassModal
        open={cleanupConfirm !== null}
        tone="rose"
        title={t.app.confirmCleanupTitle}
        description={
          cleanupConfirm
            ? t.app.confirmCleanup(
                cleanupConfirm.ids.length,
                formatBytes(cleanupConfirm.selectedBytes)
              )
            : ""
        }
        cancelLabel={t.app.btnCancel}
        confirmLabel={
          isCleaning ? t.results.btnCleaning : t.app.btnConfirmMoveTrash
        }
        isLoading={isCleaning}
        onCancel={handleCancelSmartCleanup}
        onConfirm={handleConfirmSmartCleanup}
      />

      <GlassToast
        toastId={toast?.id ?? null}
        tone={toast?.tone ?? "success"}
        message={toastMessage}
        dismissLabel={t.app.toastDismiss}
        onClose={dismissToast}
      />
    </>
  );
}
