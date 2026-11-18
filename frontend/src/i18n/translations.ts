export type Language = "vi" | "en";

export const STORAGE_KEY = "uniphoto_lang";

export type CanonicalAestheticTag =
  | "eyes_closed"
  | "face_blurry"
  | "tilted_horizon"
  | "edge_subject"
  | "eyes_open_sharp"
  | "level_horizon"
  | "rule_of_thirds";

export function getInitialLanguage(): Language {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "vi" || saved === "en") {
      return saved;
    }
  } catch {
    // Ignore storage errors
  }
  return "vi";
}

const vi = {
  app: {
    windowTitle: "UniPhoto — Tìm & Dọn dẹp Ảnh trùng lặp",
    dialogPickFolderTitle: "Chọn thư mục ảnh cần quét",
    switchLangTooltip: "Switch to English",
    bootingBadge: "Đang khởi động",
    bootTimeoutBadge: "Chưa kết nối",
    bootingTitle: "Đang khởi động bộ xử lý ảnh UniPhoto...",
    bootingSubtitle:
      "Đang nạp dịch vụ phân tích ảnh ngoại tuyến trên máy Mac của bạn, vui lòng đợi trong giây lát.",
    bootTimeoutDesc:
      "Chưa thể kết nối tới dịch vụ xử lý ảnh nền sau thời gian chờ. Vui lòng thử kết nối lại.",
    btnRetryConnect: "Thử kết nối lại",
    phaseResetting: "Đang làm mới danh sách...",
    phaseScanningDups: "Đang kiểm tra thư mục và tìm các bức ảnh trùng nhau...",
    phaseClusteringAi:
      "Đang phân tích và gom nhóm các bức ảnh có góc chụp tương tự...",
    phaseScoringAesthetics:
      "Đang chấm điểm thẩm mỹ & chất lượng (khuôn mặt, mắt nhắm, góc máy, độ nét)...",
    groupFallback: (index: number) => `Nhóm #${index}`,
    errScan: "Có lỗi xảy ra khi quét thư mục",
    errCluster: "Lỗi khi tìm ảnh tương tự",
    errAesthetic: "Lỗi khi chấm điểm thẩm mỹ ảnh tương tự",
    alertNoSelection: "Bạn chưa chọn bức ảnh nào để chuyển vào Thùng rác.",
    confirmCleanupTitle: "Chuyển ảnh đã chọn vào Thùng rác?",
    confirmCleanup: (count: number, size: string) =>
      `Chuyển ${count} ảnh đã chọn (${size}) vào Thùng rác macOS? Bạn có thể khôi phục lại từ Thùng rác bất cứ lúc nào.`,
    btnConfirmMoveTrash: "Chuyển vào Thùng rác",
    btnCancel: "Hủy",
    toastTrashedSuccess: (count: number, size: string) =>
      `Đã chuyển ${count} ảnh vào Thùng rác • Giải phóng ${size}`,
    toastAestheticSuccess: (count: number) =>
      `Đã chấm điểm thẩm mỹ cho ${count} ảnh tương tự`,
    toastCancelled:
      "Đã dừng tác vụ theo yêu cầu • Đã lưu các kết quả vừa xử lý",
    toastDismiss: "Đóng thông báo",
    errCleanup: "Lỗi khi chuyển ảnh vào Thùng rác",
  },
  api: {
    errProgress: "Không thể đọc tiến độ",
    errScan: "Lỗi khi quét thư mục",
    errCluster: "Lỗi khi gom cụm AI",
    errAesthetic: "Lỗi khi chấm điểm thẩm mỹ AI",
    errCancelScan: "Không thể gửi yêu cầu dừng tác vụ",
    errLoadClusters: "Không thể tải danh sách cụm ảnh AI",
    errLoadDuplicates: "Không thể tải danh sách ảnh trùng",
    errRescore: "Không thể chấm điểm lại chất lượng ảnh",
    errDeletePhoto: "Lỗi khi chuyển ảnh vào Thùng rác",
    errDeleteMultiple: "Lỗi khi chuyển các ảnh đã chọn vào Thùng rác",
    errResetDb: "Không thể làm sạch Database",
  },
  home: {
    viewPreviousResults: (size: string) => `Xem kết quả cũ (${size})`,
    heroTitle: "Tìm & Dọn dẹp Ảnh trùng lặp",
    heroSubtitle:
      "Chọn thư mục ảnh trên máy Mac để tự động tìm các bức ảnh bị trùng hoặc có góc chụp tương tự nhau, giải phóng dung lượng ổ cứng an toàn.",
    pickFolderTitle: "Chọn thư mục ảnh",
    pickFolderHint: "Nhấn để duyệt trong Finder hoặc kéo-thả thư mục vào đây",
    dropFolderActive: "Thả thư mục ảnh vào đây",
    selectedFolderLabel: "Thư mục đã chọn",
    changeFolderLink: "Đổi thư mục khác",
    optFindSimilar: "Tìm cả các ảnh có góc chụp tương tự",
    optClearOld: "Làm mới danh sách trước khi quét",
    btnStartScan: "Bắt đầu quét",
    btnPickAndScan: "Chọn thư mục & Quét",
    privacyFooter:
      "Mọi hình ảnh được xử lý trực tiếp và riêng tư ngay trên máy Mac của bạn",
  },
  scanning: {
    badgeClustering: "Đang gom nhóm AI",
    badgeScanning: "Đang quét ảnh",
    badgeAesthetics: "Chấm thẩm mỹ",
    badgeCancelled: "Đang dừng",
    photoProgress: (current: number, total: number) =>
      `${current} / ${total} ảnh`,
    checkingFolder: "Đang kiểm tra thư mục...",
    checkingFile: (file: string) => `Đang xử lý: ${file}`,
    folderPrefix: (folder: string) => `Thư mục: ${folder}`,
    keptPhotos: "Ảnh giữ lại:",
    duplicatePhotos: "Ảnh trùng lặp:",
    btnCancelScan: "Dừng tác vụ",
    btnCancelling: "Đang dừng...",
  },
  results: {
    btnChangeFolder: "Đổi thư mục ảnh",
    btnRefresh: "Làm mới",
    secStorage: "Lưu trữ",
    secDuplicates: "Ảnh trùng nhau",
    navAllDuplicates: "Ảnh trùng lặp",
    secSimilars: "Ảnh tương tự",
    navAllSimilars: "Ảnh tương tự",
    navSelected: "Đã chọn",
    selectedLabel: "Đã chọn",
    selectedCount: (count: number) => `${count} ảnh`,
    masterSubtitle: (groups: number, size: string) =>
      `${groups} nhóm • ${size}`,
    groupPhotosCount: (count: number) => `${count} ảnh`,
    groupSelectedCount: (checked: number, total: number) =>
      `Đã chọn ${checked}/${total}`,
    btnAutoSelect: "Chọn tự động",
    btnAutoSelectTooltip:
      "Tự động chọn các ảnh trùng và giữ lại 1 ảnh đẹp nhất mỗi nhóm (⌘A)",
    btnDeselectAll: "Bỏ chọn tất cả",
    sortBySize: "Sắp xếp theo dung lượng",
    sortByCount: "Sắp xếp theo số lượng ảnh",
    emptyGroups: "Không có nhóm ảnh nào trong danh mục này.",
    loadingMoreGroups: "Đang tải thêm nhóm ảnh...",
    btnLoadMoreGroups: (loaded: number, total: number) =>
      `Tải thêm (${loaded}/${total})`,
    disconnectedVolumesNotice: (volumes: string) =>
      `Ổ đĩa ngoài đang ngắt kết nối (${volumes}) — Đã tạm ẩn và bảo toàn dữ liệu quét cho đến khi cắm lại.`,
    badgeKeepShort: "Giữ",
    badgeKeepTooltip: "Bản đề xuất giữ lại",
    bestPhotoBadge: "Đề xuất giữ",
    recommendedKeepBadge: "Đề xuất giữ",
    btnShowSidebar: "Hiện thanh bên",
    btnHideSidebar: "Ẩn thanh bên",
    viewSingle: "Xem lớn",
    viewGrid: "So sánh",
    btnOpenPreview: "Preview",
    btnOpenFinder: "Finder",
    btnOpenGroup: "Mở nhóm",
    btnFindSimilars: "Tìm ảnh tương tự",
    btnScoreAesthetics: "Chấm điểm thẩm mỹ",
    btnRescoreAesthetics: "Chấm lại thẩm mỹ",
    btnScoreAestheticsTooltip:
      "Phân tích khuôn mặt & mắt nhắm, góc nghiêng máy, bố cục và độ sắc nét cho các nhóm ảnh tương tự",
    aestheticBannerTitle:
      "Chấm điểm thẩm mỹ & chất lượng ảnh tương tự (Tùy chọn)",
    aestheticBannerDesc:
      "Đánh giá khuôn mặt & mắt nhắm, góc máy nghiêng, bố cục 1/3 và độ sắc nét để chọn bức ảnh đẹp nhất trong từng loạt chụp.",
    btnDismissBanner: "Ẩn gợi ý",
    btnShortcuts: "Phím tắt",
    btnShortcutsTooltip: "Xem danh sách phím tắt bàn phím",
    shortcutsTitle: "Phím tắt bàn phím",
    shortcutSearchFocus: "Tìm kiếm nhanh tên ảnh / thư mục",
    shortcutPrevNextPhoto: "Ảnh trước / tiếp theo trong nhóm",
    shortcutPrevNextGroup: "Nhóm ảnh trước / tiếp theo",
    shortcutToggleSelect: "Chọn / bỏ chọn ảnh đang xem",
    shortcutSwitchView: "Chuyển Xem lớn / So sánh",
    shortcutOpenPreview: "Mở ảnh trong macOS Preview",
    shortcutRevealFinder: "Hiển thị ảnh trong Finder",
    shortcutAutoSelect: "Chọn tự động trong mục hiện tại",
    shortcutEscape: "Đóng bảng phím tắt / Xóa tìm kiếm",
    searchPlaceholder: "Tìm kiếm",
    btnClearSearch: "Xóa tìm kiếm",
    emptySelectionTitle: "Chưa chọn nhóm ảnh nào",
    emptySelectionPrompt:
      "Chọn một nhóm ảnh từ danh sách bên trái để xem chi tiết, hoặc nhấn ⌘F để tìm kiếm nhanh.",
    statSelectedLine1: "ảnh chọn",
    statSelectedLine2: "vào Thùng rác",
    statTotalLine1: "ảnh trong",
    statTotalLine2: "nhóm này",
    scoreLabel: "Chất lượng",
    techScoreShortLabel: "Kỹ thuật",
    aestheticScoreLabel: "Điểm thẩm mỹ",
    metricSharpness: "Độ nét",
    metricExposure: "Ánh sáng",
    metricContrast: "Tương phản",
    metricComposition: "Bố cục & Góc máy",
    metricFace: "Góc mặt & Mắt",
    tiltDeg: (deg: string) => `Lệch ${deg}°`,
    reasonHighestRes: "Độ phân giải cao nhất",
    reasonSharpest: "Sắc nét nhất",
    reasonBestExposure: "Ánh sáng tốt nhất",
    reasonBestContrast: "Tương phản tốt nhất",
    reasonLeastCompressed: "Ít nén nhất",
    reasonBestOverall: "Chất lượng tổng thể tốt nhất",
    reasonLargestFile: "Dung lượng lớn nhất",
    reasonEyesOpen: "Mắt mở rõ, không chớp",
    reasonFaceSharp: "Khuôn mặt rõ nét hơn",
    reasonLevelCamera: "Góc máy cân bằng, không nghiêng",
    reasonBetterComposition: "Bố cục hài hòa hơn",
    reasonBestAesthetics: "Thẩm mỹ tổng thể đẹp nhất",
    aestheticTags: {
      eyes_closed: "Nhắm mắt",
      face_blurry: "Mặt bị mờ",
      tilted_horizon: "Nghiêng góc máy",
      edge_subject: "Chủ thể sát mép",
      eyes_open_sharp: "Mắt mở sắc nét",
      level_horizon: "Góc máy thẳng",
      rule_of_thirds: "Bố cục 1/3",
    } satisfies Record<CanonicalAestheticTag, string>,
    statusSelectedToDelete: "Đã chọn chuyển vào Thùng rác",
    statusKeepingClickToDelete: "Đang giữ lại (Nhấn để chọn dọn)",
    filmstripSuggestedKeep: "• Đề xuất giữ",
    cardSuggestedKeep: "Đề xuất giữ lại",
    cardPhotoIndex: (idx: number) => `Ảnh #${idx}`,
    cardFolderPrefix: "Thư mục:",
    footerFoundPrefix: "Tổng cộng",
    footerInMiddle: "trong",
    footerPhotosSuffix: (count: number) => (count >= 0 ? "ảnh" : "ảnh"),
    btnShowInFinder: "Hiện trong Finder",
    btnCleaning: "Đang chuyển vào Thùng rác...",
    btnFreeUp: (size: string) => `Chuyển vào Thùng rác (${size})`,
    btnFreeUpTooltip:
      "Chuyển an toàn các ảnh đã chọn vào Thùng rác macOS (có thể khôi phục bất cứ lúc nào)",
  },
};

export type Translations = typeof vi;

const en: Translations = {
  app: {
    windowTitle: "UniPhoto — Duplicate & Similar Photo Cleaner",
    dialogPickFolderTitle: "Select photo folder to scan",
    switchLangTooltip: "Chuyển sang Tiếng Việt",
    bootingBadge: "Starting Engine",
    bootTimeoutBadge: "Connection Timeout",
    bootingTitle: "Starting UniPhoto Photo Engine...",
    bootingSubtitle:
      "Loading local offline photo analysis services on your Mac, this will only take a moment.",
    bootTimeoutDesc:
      "Could not connect to the local photo engine in time. Please try reconnecting.",
    btnRetryConnect: "Retry Connection",
    phaseResetting: "Clearing previous scan data...",
    phaseScanningDups: "Scanning folder and finding exact duplicate photos...",
    phaseClusteringAi:
      "Analyzing and grouping visually similar photos with AI...",
    phaseScoringAesthetics:
      "Scoring similar photos (face & closed eyes, camera tilt, composition & sharpness)...",
    groupFallback: (index: number) => `Group #${index}`,
    errScan: "An error occurred while scanning the folder",
    errCluster: "Failed to find similar photos",
    errAesthetic: "Failed to run aesthetic scoring",
    alertNoSelection: "Please select at least one photo to move to Trash.",
    confirmCleanupTitle: "Move selected photos to Trash?",
    confirmCleanup: (count: number, size: string) =>
      `Move ${count} selected ${
        count === 1 ? "photo" : "photos"
      } (${size}) to macOS Trash? You can restore ${
        count === 1 ? "it" : "them"
      } from Trash anytime.`,
    btnConfirmMoveTrash: "Move to Trash",
    btnCancel: "Cancel",
    toastTrashedSuccess: (count: number, size: string) =>
      `Moved ${count} ${count === 1 ? "photo" : "photos"} to Trash • Freed ${size}`,
    toastAestheticSuccess: (count: number) =>
      `Scored aesthetics for ${count} similar ${count === 1 ? "photo" : "photos"}`,
    toastCancelled: "Task stopped as requested • Saved processed results",
    toastDismiss: "Dismiss notification",
    errCleanup: "Failed to move selected photos to Trash",
  },
  api: {
    errProgress: "Unable to read scan progress",
    errScan: "Error scanning folder",
    errCluster: "Error clustering photos with AI",
    errAesthetic: "Error scoring photo aesthetics",
    errCancelScan: "Unable to stop current task",
    errLoadClusters: "Unable to load AI photo clusters",
    errLoadDuplicates: "Unable to load duplicate groups",
    errRescore: "Unable to re-score photo quality",
    errDeletePhoto: "Error moving photo to Trash",
    errDeleteMultiple: "Error moving selected photos to Trash",
    errResetDb: "Unable to reset database",
  },
  home: {
    viewPreviousResults: (size: string) => `Previous scan (${size})`,
    heroTitle: "Find & Clean Duplicate Photos",
    heroSubtitle:
      "Select a photo folder on your Mac to automatically detect exact duplicates and similar-angle shots, freeing up disk space safely.",
    pickFolderTitle: "Select Photo Folder",
    pickFolderHint: "Click to browse in Finder or drag & drop a folder here",
    dropFolderActive: "Drop photo folder here",
    selectedFolderLabel: "Selected Folder",
    changeFolderLink: "Choose another folder",
    optFindSimilar: "Also find visually similar photos",
    optClearOld: "Clear previous results before scanning",
    btnStartScan: "Start Scan",
    btnPickAndScan: "Select Folder & Scan",
    privacyFooter:
      "All photos are processed locally and privately on your Mac",
  },
  scanning: {
    badgeClustering: "AI Grouping",
    badgeScanning: "Scanning",
    badgeAesthetics: "Aesthetics",
    badgeCancelled: "Stopping",
    photoProgress: (current: number, total: number) =>
      `${current} / ${total} photos`,
    checkingFolder: "Checking folder...",
    checkingFile: (file: string) => `Processing: ${file}`,
    folderPrefix: (folder: string) => `Folder: ${folder}`,
    keptPhotos: "Kept:",
    duplicatePhotos: "Duplicates:",
    btnCancelScan: "Stop Task",
    btnCancelling: "Stopping...",
  },
  results: {
    btnChangeFolder: "Change Folder",
    btnRefresh: "Refresh",
    secStorage: "Storage",
    secDuplicates: "Exact Duplicates",
    navAllDuplicates: "Duplicates",
    secSimilars: "Similar Photos",
    navAllSimilars: "Similar Photos",
    navSelected: "Selected",
    selectedLabel: "Selected",
    selectedCount: (count: number) =>
      `${count} ${count === 1 ? "photo" : "photos"}`,
    masterSubtitle: (groups: number, size: string) =>
      `${groups} ${groups === 1 ? "group" : "groups"} • ${size}`,
    groupPhotosCount: (count: number) =>
      `${count} ${count === 1 ? "photo" : "photos"}`,
    groupSelectedCount: (checked: number, total: number) =>
      `Selected ${checked}/${total}`,
    btnAutoSelect: "Auto Select",
    btnAutoSelectTooltip:
      "Automatically select duplicates while keeping the best photo in each group (⌘A)",
    btnDeselectAll: "Deselect All",
    sortBySize: "Sort by Size",
    sortByCount: "Sort by Photo Count",
    emptyGroups: "No photo groups in this category.",
    loadingMoreGroups: "Loading more photo groups...",
    btnLoadMoreGroups: (loaded: number, total: number) =>
      `Load more (${loaded}/${total})`,
    disconnectedVolumesNotice: (volumes: string) =>
      `External drive disconnected (${volumes}) — Scan data for this drive is safely preserved until reconnected.`,
    badgeKeepShort: "Keep",
    badgeKeepTooltip: "Recommended to keep",
    bestPhotoBadge: "Best Shot",
    recommendedKeepBadge: "Recommended Keep",
    btnShowSidebar: "Show Sidebar",
    btnHideSidebar: "Hide Sidebar",
    viewSingle: "Large View",
    viewGrid: "Compare",
    btnOpenPreview: "Preview",
    btnOpenFinder: "Finder",
    btnOpenGroup: "Open Group",
    btnFindSimilars: "Find Similar",
    btnScoreAesthetics: "Score Aesthetics",
    btnRescoreAesthetics: "Re-score Aesthetics",
    btnScoreAestheticsTooltip:
      "Analyze face & closed eyes, camera tilt, composition, and sharpness across similar photo groups",
    aestheticBannerTitle:
      "AI Aesthetic & Quality Scoring for Similar Photos (Optional)",
    aestheticBannerDesc:
      "Evaluate face & closed eyes, camera tilt, composition, and sharpness/quality to pick the best shot in each similar group.",
    btnDismissBanner: "Dismiss",
    btnShortcuts: "Shortcuts",
    btnShortcutsTooltip: "View keyboard shortcuts",
    shortcutsTitle: "Keyboard Shortcuts",
    shortcutSearchFocus: "Focus search bar",
    shortcutPrevNextPhoto: "Previous / next photo in group",
    shortcutPrevNextGroup: "Previous / next group",
    shortcutToggleSelect: "Select / deselect current photo",
    shortcutSwitchView: "Switch Large View / Compare",
    shortcutOpenPreview: "Open in macOS Preview",
    shortcutRevealFinder: "Reveal photo in Finder",
    shortcutAutoSelect: "Auto-select in current tab",
    shortcutEscape: "Close popover / Clear search",
    searchPlaceholder: "Search",
    btnClearSearch: "Clear search",
    emptySelectionTitle: "No Photo Group Selected",
    emptySelectionPrompt:
      "Select a photo group from the list on the left to inspect, or press ⌘F to search.",
    statSelectedLine1: "selected",
    statSelectedLine2: "for Trash",
    statTotalLine1: "photos in",
    statTotalLine2: "this group",
    scoreLabel: "Quality",
    techScoreShortLabel: "Tech",
    aestheticScoreLabel: "Aesthetic Score",
    metricSharpness: "Sharpness",
    metricExposure: "Exposure",
    metricContrast: "Contrast",
    metricComposition: "Composition",
    metricFace: "Face & Eyes",
    tiltDeg: (deg: string) => `Tilt ${deg}°`,
    reasonHighestRes: "Highest resolution",
    reasonSharpest: "Sharpest focus",
    reasonBestExposure: "Best exposure",
    reasonBestContrast: "Best contrast",
    reasonLeastCompressed: "Least compressed",
    reasonBestOverall: "Best overall quality",
    reasonLargestFile: "Largest file size",
    reasonEyesOpen: "Eyes open & sharp",
    reasonFaceSharp: "Sharper face",
    reasonLevelCamera: "Level camera horizon",
    reasonBetterComposition: "Better composition",
    reasonBestAesthetics: "Best overall aesthetics",
    aestheticTags: {
      eyes_closed: "Closed eyes",
      face_blurry: "Blurry face",
      tilted_horizon: "Tilted horizon",
      edge_subject: "Edge subject",
      eyes_open_sharp: "Sharp open eyes",
      level_horizon: "Level camera",
      rule_of_thirds: "Rule of thirds",
    } satisfies Record<CanonicalAestheticTag, string>,
    statusSelectedToDelete: "Selected to move to Trash",
    statusKeepingClickToDelete: "Keeping (Click to select for Trash)",
    filmstripSuggestedKeep: "• Keep",
    cardSuggestedKeep: "Recommended to keep",
    cardPhotoIndex: (idx: number) => `Photo #${idx}`,
    cardFolderPrefix: "Folder:",
    footerFoundPrefix: "Total",
    footerInMiddle: "across",
    footerPhotosSuffix: (count: number) => (count === 1 ? "photo" : "photos"),
    btnShowInFinder: "Reveal in Finder",
    btnCleaning: "Moving to Trash...",
    btnFreeUp: (size: string) => `Move to Trash (${size})`,
    btnFreeUpTooltip:
      "Safely move selected photos to macOS Trash (restorable anytime)",
  },
};

export const translations: Record<Language, Translations> = {
  vi,
  en,
};

const BACKEND_STATUS_EN_MAP: Record<string, string> = {
  "Đang chuẩn bị...": "Preparing...",
  "Đang bắt đầu quét...": "Starting scan...",
  "Hoàn tất quét thư mục": "Folder scan complete",
  "Đang khởi tạo AI MobileNetV2...": "Initializing MobileNetV2 AI...",
  "Không có ảnh cần gom cụm": "No photos to cluster",
  "Hoàn tất": "Completed",
  "Hoàn tất gom cụm AI": "AI clustering complete",
  "Đang khởi tạo chấm điểm thẩm mỹ AI...":
    "Initializing AI aesthetic scoring...",
  "Không có cụm ảnh tương tự cần chấm thẩm mỹ":
    "No similar photo clusters to score",
  "Hoàn tất chấm điểm thẩm mỹ AI": "AI aesthetic scoring complete",
  "Đã dừng quét thư mục": "Folder scan stopped",
  "Đã dừng gom cụm AI": "AI clustering stopped",
  "Đã dừng chấm điểm thẩm mỹ AI": "AI aesthetic scoring stopped",
  "Đã gửi yêu cầu dừng tác vụ.": "Cancellation requested.",
};

export function localizeBackendFileStatus(
  statusOrFile: string,
  lang: Language
): string {
  if (!statusOrFile || lang === "vi") return statusOrFile;
  return BACKEND_STATUS_EN_MAP[statusOrFile] ?? statusOrFile;
}
