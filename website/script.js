const SITE_CONFIG = {
  version: "v0.1.0",
  githubRepo: "hungtun/UniPhoto", // Đổi thành "<username>/<repo>" của bạn trên GitHub
  downloadUrlDmg: "https://github.com/hungtun/UniPhoto/releases/latest/download/UniPhoto_0.1.0_aarch64.dmg",
  downloadUrlZip: "https://github.com/hungtun/UniPhoto/releases/latest/download/UniPhoto_0.1.0_aarch64.zip",
  downloadUrlWinExe: "https://github.com/hungtun/UniPhoto/releases/latest/download/UniPhoto_0.1.0_x64-setup.exe",
  winSizeLabel: "~98 MB",
  githubUrl: "https://github.com/hungtun/UniPhoto",
  autoFetchLatestRelease: true,
};

(function () {
  "use strict";

  const LANG_STORAGE_KEY = "uniphoto_lang";
  const releaseState = {
    version: SITE_CONFIG.version,
    dmgUrl: SITE_CONFIG.downloadUrlDmg,
    zipUrl: SITE_CONFIG.downloadUrlZip,
    winUrl: SITE_CONFIG.downloadUrlWinExe,
    winSizeLabel: SITE_CONFIG.winSizeLabel,
    downloadCount: 0,
    githubUrl: SITE_CONFIG.githubUrl,
  };

  const I18N = {
    vi: {
      meta: {
        title: "UniPhoto — Dọn sạch ảnh trùng trên Mac & Windows",
        description: "Ứng dụng miễn phí cho macOS & Windows giúp lọc ảnh trùng, gom loạt chụp liên tiếp và chọn tấm sắc nét nhất. 100% Offline.",
      },
      nav: { download: "Tải về" },
      hero: {
        title: "Dọn sạch ảnh trùng trên Mac & Windows.",
        subtitle: "Lọc ảnh trùng, gom loạt chụp liên tiếp và chọn tấm sắc nét nhất.",
        ctaDmg: "Tải cho macOS",
        ctaWin: "Tải cho Windows",
        zipLink: "macOS .zip",
        reqOs: "macOS 12+ & Windows 10/11",
        reqFree: "Miễn phí & 100% Offline",
        downloadsUnit: "lượt tải",
      },
      mockup: {
        secLibrary: "Danh mục",
        navDuplicates: "Ảnh trùng lặp",
        navSimilars: "Ảnh tương tự",
        navSelected: "Đã chọn",
        secStorage: "Lưu trữ",
        statusReady: "UniPhoto • Sẵn sàng",
        searchPlaceholder: "Tìm kiếm",
        viewSingle: "Xem lớn",
        viewCompare: "So sánh",
        btnAiScored: "Điểm AI",
      },
      mockupDynamic: {
        recommendedKeepLargest: "✓ Giữ bản lớn nhất",
        keepShort: "Giữ",
        selectedForTrash: "Chọn dọn",
        keepingClickToSelect: "Đang giữ",
        techLabel: "Độ nét",
        compBarLabel: "Bố cục",
        faceBarLabel: "Khuôn mặt",
        groupsUnit: "nhóm",
        photosUnit: "ảnh",
        moveToTrashPrefix: "Chuyển vào Thùng rác",
        footerTotalPrefix: "Tổng",
        emptySelected: "Chưa chọn ảnh nào.",
        toastTrashDemo: "Đã chuyển vào Thùng rác macOS (có thể hoàn tác Put Back).",
        toastAutoSelected: "Đã chọn ảnh thừa, giữ lại 1 tấm tốt nhất mỗi nhóm.",
        toastAiInfo: "AI chấm mắt mở, độ nét và góc máy cho Ảnh tương tự.",
        tags: {
          eyes_open_sharp: "Mắt mở nét",
          level_horizon: "Góc thẳng",
          rule_of_thirds: "Bố cục 1/3",
          eyes_closed: "Nhắm mắt",
          tilted_horizon: "Nghiêng góc",
          edge_subject: "Sát mép",
          face_blurry: "Mặt mờ",
        },
      },
      features: {
        c1Title: "Giao diện Desktop gốc",
        c1Desc: "Ba cột trực quan, phím tắt nhanh và kéo-thả thư mục.",
        c2Title: "Lọc trùng tức thì",
        c2Desc: "Tự động giữ lại file gốc có dung lượng lớn nhất.",
        c3Title: "AI chọn ảnh đẹp",
        c3Desc: "Phát hiện mắt nhắm, mặt mờ và góc máy bị nghiêng.",
        c4Title: "An toàn & Offline",
        c4Desc: "Chuyển vào Thùng rác hệ thống, không tải ảnh lên mạng.",
      },
      install: {
        title: "Mở lần đầu trên macOS",
        desc: "Kéo UniPhoto vào Applications. Nếu macOS hỏi xác minh lần đầu, chạy lệnh sau trong Terminal:",
        btnCopy: "Sao chép",
        btnCopied: "Đã chép ✓",
      },
      footer: { note: "Miễn phí cho macOS & Windows" },
    },
    en: {
      meta: {
        title: "UniPhoto — Clean duplicate photos on Mac & Windows",
        description: "Free desktop app for macOS & Windows to find exact duplicates, group burst shots, and keep your sharpest frame. 100% Offline.",
      },
      nav: { download: "Download" },
      hero: {
        title: "Clean duplicate photos on Mac & Windows.",
        subtitle: "Find exact duplicates, group burst shots, and keep your sharpest frame.",
        ctaDmg: "Download for macOS",
        ctaWin: "Download for Windows",
        zipLink: "macOS .zip",
        reqOs: "macOS 12+ & Windows 10/11",
        reqFree: "Free & 100% Offline",
        downloadsUnit: "downloads",
      },
      mockup: {
        secLibrary: "Library",
        navDuplicates: "Duplicates",
        navSimilars: "Similar Photos",
        navSelected: "Selected",
        secStorage: "Storage",
        statusReady: "UniPhoto • Ready",
        searchPlaceholder: "Search",
        viewSingle: "Large View",
        viewCompare: "Compare",
        btnAiScored: "AI Score",
      },
      mockupDynamic: {
        recommendedKeepLargest: "✓ Keep largest",
        keepShort: "Keep",
        selectedForTrash: "Move to Trash",
        keepingClickToSelect: "Keeping",
        techLabel: "Sharpness",
        compBarLabel: "Framing",
        faceBarLabel: "Face",
        groupsUnit: "groups",
        photosUnit: "photos",
        moveToTrashPrefix: "Move to Trash",
        footerTotalPrefix: "Total",
        emptySelected: "No photos selected.",
        toastTrashDemo: "Moved to macOS Trash (restorable via Put Back).",
        toastAutoSelected: "Selected extras, keeping the best shot per group.",
        toastAiInfo: "AI scores open eyes, sharpness, and horizon on Similar Photos.",
        tags: {
          eyes_open_sharp: "Sharp eyes",
          level_horizon: "Level horizon",
          rule_of_thirds: "Rule of thirds",
          eyes_closed: "Closed eyes",
          tilted_horizon: "Tilted",
          edge_subject: "Edge subject",
          face_blurry: "Blurry face",
        },
      },
      features: {
        c1Title: "Native Desktop UI",
        c1Desc: "Clean split-view, keyboard shortcuts, and folder drag & drop.",
        c2Title: "Instant Duplicates",
        c2Desc: "Automatically keeps the largest original file.",
        c3Title: "Smart Burst AI",
        c3Desc: "Spots closed eyes, blurry faces, and tilted horizons.",
        c4Title: "Safe & 100% Offline",
        c4Desc: "Moves to Trash / Recycle Bin. 100% local.",
      },
      install: {
        title: "First launch on macOS",
        desc: "Drag UniPhoto to Applications. If Gatekeeper prompts on first launch, run in Terminal:",
        btnCopy: "Copy",
        btnCopied: "Copied ✓",
      },
      footer: { note: "Free for macOS & Windows" },
    },
  };

  function renderSceneSvg(sceneKey) {
    switch (sceneKey) {
      case "bridge":
        return `<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="bgBridge" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#1E1B4B"/><stop offset="52%" stop-color="#C2410C"/><stop offset="100%" stop-color="#FBBF24"/></linearGradient></defs><rect width="400" height="250" fill="url(#bgBridge)"/><circle cx="275" cy="92" r="34" fill="#FDE68A" opacity="0.92"/><path d="M0 175 Q95 130 205 162 T400 148 L400 250 L0 250 Z" fill="#312E81" opacity="0.72"/><path d="M0 198 Q130 165 260 190 T400 182 L400 250 L0 250 Z" fill="#1E1B4B"/><path d="M35 168 Q200 112 365 168" fill="none" stroke="#FCD34D" stroke-width="6" stroke-linecap="round"/><path d="M35 173 Q200 117 365 173" fill="none" stroke="#FEF3C7" stroke-width="1.6" opacity="0.8"/></svg>`;
      case "halong":
        return `<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="skyHalong" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#0F172A"/><stop offset="55%" stop-color="#0E7490"/><stop offset="100%" stop-color="#67E8F9"/></linearGradient><linearGradient id="seaHalong" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#0D9488"/><stop offset="100%" stop-color="#064E3B"/></linearGradient></defs><rect width="400" height="150" fill="url(#skyHalong)"/><rect y="150" width="400" height="100" fill="url(#seaHalong)"/><path d="M45 150 L75 78 L112 96 L138 66 L172 150 Z" fill="#115E59"/><path d="M215 150 L248 84 L278 105 L306 74 L344 150 Z" fill="#134E4A"/><ellipse cx="195" cy="198" rx="34" ry="5" fill="#F97316"/><line x1="175" y1="191" x2="215" y2="205" stroke="#FDE68A" stroke-width="2.5"/></svg>`;
      case "hoian":
        return `<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg"><rect width="400" height="250" fill="#131126"/><rect y="168" width="400" height="82" fill="#0B0A17"/><line x1="20" y1="45" x2="380" y2="62" stroke="#4B5563" stroke-width="1.5"/><circle cx="88" cy="72" r="16" fill="#EF4444"/><circle cx="158" cy="78" r="18" fill="#F59E0B"/><circle cx="235" cy="76" r="17" fill="#10B981"/><circle cx="312" cy="82" r="16" fill="#EC4899"/><ellipse cx="88" cy="196" rx="14" ry="4" fill="#EF4444" opacity="0.45"/><ellipse cx="158" cy="202" rx="18" ry="5" fill="#F59E0B" opacity="0.5"/><ellipse cx="235" cy="200" rx="16" ry="4" fill="#10B981" opacity="0.45"/><ellipse cx="312" cy="205" rx="14" ry="4" fill="#EC4899" opacity="0.45"/></svg>`;
      case "portrait_good":
      case "portrait_blink":
      case "portrait_tilt": {
        const isBlink = sceneKey === "portrait_blink";
        const isTilt = sceneKey === "portrait_tilt";
        const rot = isTilt ? 'transform="rotate(6.3 200 125)"' : "";
        const eyes = isBlink
          ? `<path d="M178 106 Q186 112 194 106" fill="none" stroke="#1E293B" stroke-width="2.6" stroke-linecap="round"/><path d="M206 106 Q214 112 222 106" fill="none" stroke="#1E293B" stroke-width="2.6" stroke-linecap="round"/>`
          : `<circle cx="186" cy="105" r="3.6" fill="#0F172A"/><circle cx="187.2" cy="103.8" r="1.1" fill="#FFF"/><circle cx="214" cy="105" r="3.6" fill="#0F172A"/><circle cx="215.2" cy="103.8" r="1.1" fill="#FFF"/>`;
        const guide = isTilt ? `<line x1="24" y1="158" x2="376" y2="158" stroke="#FBBF24" stroke-width="1.3" stroke-dasharray="5 5" opacity="0.75"/>` : "";
        return `<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="bgP_${sceneKey}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#1E3A5F"/><stop offset="65%" stop-color="#3B82F6"/><stop offset="100%" stop-color="#93C5FD"/></linearGradient></defs><rect width="400" height="250" fill="#0F172A"/><g ${rot}><rect x="-30" y="-30" width="460" height="205" fill="url(#bgP_${sceneKey})"/><rect x="-30" y="158" width="460" height="130" fill="#14532D"/><path d="M-20 158 L70 112 L150 158 Z" fill="#1E293B" opacity="0.45"/><path d="M250 158 L335 104 L420 158 Z" fill="#1E293B" opacity="0.45"/><path d="M136 255 C142 188 258 188 264 255 Z" fill="#2563EB"/><circle cx="200" cy="106" r="36" fill="#FDE2C8"/><path d="M162 98 C164 62 236 62 238 98 C226 82 174 82 162 98 Z" fill="#1E1B24"/>${eyes}<path d="M191 122 Q200 129 209 122" fill="none" stroke="#B45309" stroke-width="2.2" stroke-linecap="round"/></g>${guide}</svg>`;
      }
      case "sailboat_good":
      case "sailboat_tilt":
      case "sailboat_edge": {
        const rot = sceneKey === "sailboat_tilt" ? 'transform="rotate(-6.5 200 125)"' : "";
        const boatX = sceneKey === "sailboat_edge" ? 344 : 252;
        const guide = sceneKey === "sailboat_tilt" ? `<line x1="20" y1="152" x2="380" y2="152" stroke="#FBBF24" stroke-width="1.3" stroke-dasharray="5 5" opacity="0.75"/>` : "";
        return `<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="skyS_${sceneKey}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#1E1B4B"/><stop offset="58%" stop-color="#DB2777"/><stop offset="100%" stop-color="#FB923C"/></linearGradient></defs><rect width="400" height="250" fill="#0F172A"/><g ${rot}><rect x="-35" y="-35" width="470" height="190" fill="url(#skyS_${sceneKey})"/><circle cx="132" cy="118" r="26" fill="#FDE047" opacity="0.9"/><rect x="-35" y="152" width="470" height="135" fill="#1E3A8A"/><g transform="translate(${boatX}, 148)"><polygon points="0,-58 0,-6 34,-6" fill="#F8FAFC"/><polygon points="-4,-48 -4,-6 -26,-6" fill="#E2E8F0"/><polygon points="-32,-2 38,-2 26,9 -22,9" fill="#7C2D12"/></g></g>${guide}</svg>`;
      }
      case "coffee_good":
      case "coffee_blur": {
        const blur = sceneKey === "coffee_blur" ? 'filter="url(#mbFilter)"' : "";
        return `<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg"><defs><filter id="mbFilter"><feGaussianBlur stdDeviation="3.4 0.9"/></filter></defs><rect width="400" height="250" fill="#1C1917"/><g ${blur}><rect x="30" y="24" width="145" height="165" rx="8" fill="#44403C" opacity="0.6"/><circle cx="315" cy="64" r="22" fill="#FBBF24" opacity="0.35"/><path d="M138 250 C145 190 255 190 262 250 Z" fill="#0D9488"/><circle cx="200" cy="112" r="34" fill="#FED7AA"/><path d="M165 104 C168 70 232 70 235 104 Z" fill="#292524"/><circle cx="187" cy="111" r="3.3" fill="#1C1917"/><circle cx="213" cy="111" r="3.3" fill="#1C1917"/><path d="M192 126 Q200 132 208 126" fill="none" stroke="#9A3412" stroke-width="2.2" stroke-linecap="round"/></g></svg>`;
      }
      default:
        return `<svg viewBox="0 0 400 250" xmlns="http://www.w3.org/2000/svg"><rect width="400" height="250" fill="#18181B"/></svg>`;
    }
  }

  function createInitialGroups() {
    return [
      {
        id: "dup-1", kind: "duplicates", title: "CauVang_BinhMinh", thumbScene: "bridge",
        photos: [
          { id: "d1-p1", name: "IMG_4082_Original.HEIC", sizeMb: 9.8, dims: "4032 × 3024", scene: "bridge", isKeep: true, selected: false },
          { id: "d1-p2", name: "IMG_4082_Copy.JPG", sizeMb: 4.2, dims: "4032 × 3024", scene: "bridge", isKeep: false, selected: true },
          { id: "d1-p3", name: "IMG_4082_Zalo_HD.JPG", sizeMb: 2.6, dims: "2560 × 1920", scene: "bridge", isKeep: false, selected: true },
        ],
      },
      {
        id: "dup-2", kind: "duplicates", title: "VinhHaLong_Kayak", thumbScene: "halong",
        photos: [
          { id: "d2-p1", name: "DSC_1190_Master.JPG", sizeMb: 11.2, dims: "6000 × 4000", scene: "halong", isKeep: true, selected: false },
          { id: "d2-p2", name: "DSC_1190_Backup.JPG", sizeMb: 7.2, dims: "6000 × 4000", scene: "halong", isKeep: false, selected: true },
        ],
      },
      {
        id: "dup-3", kind: "duplicates", title: "PhoCo_HoiAn_Dem", thumbScene: "hoian",
        photos: [
          { id: "d3-p1", name: "IMG_5510_iPhone16.HEIC", sizeMb: 8.4, dims: "4032 × 3024", scene: "hoian", isKeep: true, selected: false },
          { id: "d3-p2", name: "IMG_5510_Exported.PNG", sizeMb: 5.2, dims: "2048 × 1536", scene: "hoian", isKeep: false, selected: true },
        ],
      },
      {
        id: "sim-1", kind: "similars", title: "ChanDung_HoXuanHuong", thumbScene: "portrait_good", bestScore: 88.4,
        photos: [
          { id: "s1-p1", name: "IMG_8821_SharpOpen.HEIC", sizeMb: 8.6, dims: "4032 × 3024", scene: "portrait_good", isKeep: true, selected: false, aesthetic: 88.4, tech: 91.2, compBar: 92, faceBar: 95, tags: [{ key: "eyes_open_sharp", tone: "positive" }, { key: "level_horizon", tone: "positive" }] },
          { id: "s1-p2", name: "IMG_8822_Blink.HEIC", sizeMb: 8.1, dims: "4032 × 3024", scene: "portrait_blink", isKeep: false, selected: true, aesthetic: 54.2, tech: 84.0, compBar: 86, faceBar: 22, closedEyes: true, tags: [{ key: "eyes_closed", tone: "warn" }] },
          { id: "s1-p3", name: "IMG_8823_Tilted.HEIC", sizeMb: 7.9, dims: "4032 × 3024", scene: "portrait_tilt", isKeep: false, selected: true, aesthetic: 63.8, tech: 86.5, compBar: 44, faceBar: 88, tags: [{ key: "tilted_horizon", tone: "amber", deg: 6.3 }] },
        ],
      },
      {
        id: "sim-2", kind: "similars", title: "ThuyenBuom_HoangHon", thumbScene: "sailboat_good", bestScore: 91.0,
        photos: [
          { id: "s2-p1", name: "IMG_3051_Sailboat_Sharp.JPG", sizeMb: 8.0, dims: "4032 × 3024", scene: "sailboat_good", isKeep: true, selected: false, aesthetic: 91.0, tech: 92.4, compBar: 94, faceBar: null, tags: [{ key: "level_horizon", tone: "positive" }, { key: "rule_of_thirds", tone: "positive" }] },
          { id: "s2-p2", name: "IMG_3054_Sailboat_Tilted.JPG", sizeMb: 7.5, dims: "4032 × 3024", scene: "sailboat_tilt", isKeep: false, selected: true, aesthetic: 64.5, tech: 87.1, compBar: 41, faceBar: null, tags: [{ key: "tilted_horizon", tone: "amber", deg: 6.5 }] },
          { id: "s2-p3", name: "IMG_3055_Sailboat_Edge.JPG", sizeMb: 7.3, dims: "4032 × 3024", scene: "sailboat_edge", isKeep: false, selected: true, aesthetic: 68.2, tech: 79.4, compBar: 52, faceBar: null, tags: [{ key: "edge_subject", tone: "amber" }] },
        ],
      },
      {
        id: "sim-3", kind: "similars", title: "PhoCo_CaPheSang", thumbScene: "coffee_good", bestScore: 86.7,
        photos: [
          { id: "s3-p1", name: "IMG_2011_Portrait_Crisp.HEIC", sizeMb: 8.7, dims: "4032 × 3024", scene: "coffee_good", isKeep: true, selected: false, aesthetic: 86.7, tech: 89.5, compBar: 88, faceBar: 91, tags: [{ key: "eyes_open_sharp", tone: "positive" }, { key: "rule_of_thirds", tone: "positive" }] },
          { id: "s3-p2", name: "IMG_2012_MotionBlur.HEIC", sizeMb: 8.1, dims: "4032 × 3024", scene: "coffee_blur", isKeep: false, selected: true, aesthetic: 57.4, tech: 58.2, compBar: 78, faceBar: 44, tags: [{ key: "face_blurry", tone: "warn" }] },
        ],
      },
    ];
  }

  let currentLang = "vi";
  try {
    const saved = localStorage.getItem(LANG_STORAGE_KEY);
    if (saved === "vi" || saved === "en") currentLang = saved;
  } catch {}

  const mockupState = {
    tab: "duplicates",
    viewMode: "single",
    activeGroupId: "dup-1",
    activePhotoId: "d1-p1",
    groups: createInitialGroups(),
    toastTimer: null,
  };

  const fmtNum = (val, dec) => (currentLang === "vi" ? Number(val).toFixed(dec).replace(".", ",") : Number(val).toFixed(dec));
  const fmtMb = (val) => `${fmtNum(val, 1)} MB`;
  const getNested = (dict, key) => key.split(".").reduce((acc, k) => (acc && acc[k] !== undefined ? acc[k] : undefined), dict);

  function applyLanguage(lang) {
    currentLang = lang === "en" ? "en" : "vi";
    const dict = I18N[currentLang];
    document.documentElement.lang = currentLang;
    try { localStorage.setItem(LANG_STORAGE_KEY, currentLang); } catch {}

    document.querySelectorAll("[data-lang-btn]").forEach((btn) => {
      const active = btn.getAttribute("data-lang-btn") === currentLang;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const val = getNested(dict, el.getAttribute("data-i18n"));
      if (typeof val === "string") el.textContent = val;
    });
    document.querySelectorAll("[data-i18n-content]").forEach((el) => {
      const val = getNested(dict, el.getAttribute("data-i18n-content"));
      if (typeof val === "string") el.setAttribute("content", val);
    });
    renderDownloadCount();
    renderMockup();
  }

  function getFilteredGroups() {
    if (mockupState.tab === "duplicates") return mockupState.groups.filter((g) => g.kind === "duplicates");
    if (mockupState.tab === "similars") return mockupState.groups.filter((g) => g.kind === "similars");
    return mockupState.groups.filter((g) => g.photos.some((p) => p.selected));
  }

  function ensureValidMockupSelection(visibleGroups) {
    if (!visibleGroups.length) return null;
    let group = visibleGroups.find((g) => g.id === mockupState.activeGroupId) || visibleGroups[0];
    mockupState.activeGroupId = group.id;
    let photo = group.photos.find((p) => p.id === mockupState.activePhotoId) || group.photos[0];
    mockupState.activePhotoId = photo.id;
    return { group, photo };
  }

  function formatTagLabel(tag, md) {
    const base = md.tags[tag.key] || tag.key;
    return tag.deg !== undefined ? `${base} • ${fmtNum(tag.deg, 1)}°` : base;
  }

  function showMockupToast(message) {
    const toastEl = document.getElementById("mockupToast");
    const toastTextEl = document.getElementById("mockupToastText");
    if (!toastEl || !toastTextEl) return;
    toastTextEl.textContent = message;
    toastEl.hidden = false;
    if (mockupState.toastTimer) clearTimeout(mockupState.toastTimer);
    mockupState.toastTimer = setTimeout(() => { toastEl.hidden = true; }, 3200);
  }

  function renderMockup() {
    const dict = I18N[currentLang];
    const md = dict.mockupDynamic;
    let totalBytesMb = 0, totalPhotos = 0, selectedBytesMb = 0, selectedCount = 0;

    mockupState.groups.forEach((g) => g.photos.forEach((p) => {
      totalBytesMb += p.sizeMb;
      totalPhotos += 1;
      if (p.selected) { selectedBytesMb += p.sizeMb; selectedCount += 1; }
    }));

    document.querySelectorAll("[data-mockup-tab]").forEach((btn) => {
      btn.classList.toggle("is-active", btn.getAttribute("data-mockup-tab") === mockupState.tab);
    });

    const dupCount = document.querySelector('[data-mockup-tab="duplicates"] .mac-nav-count');
    const simCount = document.querySelector('[data-mockup-tab="similars"] .mac-nav-count');
    const selCount = document.getElementById("mockupSelectedNavCount");
    if (dupCount) dupCount.textContent = fmtMb(48.6);
    if (simCount) simCount.textContent = fmtMb(64.2);
    if (selCount) selCount.textContent = `${selectedCount} ${md.photosUnit}`;

    const selBytesEl = document.getElementById("mockupSelectedBytesLabel");
    const storageFill = document.getElementById("mockupStorageFill");
    if (selBytesEl) selBytesEl.textContent = fmtMb(selectedBytesMb);
    if (storageFill) storageFill.style.width = `${Math.min(100, Math.max(6, (selectedBytesMb / totalBytesMb) * 100)).toFixed(1)}%`;

    document.querySelectorAll("[data-mockup-view]").forEach((btn) => {
      btn.classList.toggle("is-active", btn.getAttribute("data-mockup-view") === mockupState.viewMode);
    });

    const visibleGroups = getFilteredGroups();
    const activePair = ensureValidMockupSelection(visibleGroups);
    const tabTitleMap = { duplicates: dict.mockup.navDuplicates, similars: dict.mockup.navSimilars, selected: dict.mockup.navSelected };
    const visibleBytes = visibleGroups.reduce((sum, g) => sum + g.photos.reduce((s, p) => s + p.sizeMb, 0), 0);

    const masterTitleEl = document.getElementById("mockupMasterTitle");
    const masterSubEl = document.getElementById("mockupMasterSubtitle");
    if (masterTitleEl) masterTitleEl.textContent = tabTitleMap[mockupState.tab];
    if (masterSubEl) masterSubEl.textContent = `${visibleGroups.length} ${md.groupsUnit} • ${fmtMb(visibleBytes)}`;

    const aiBtn = document.getElementById("mockupAiScoreBtn");
    if (aiBtn) aiBtn.hidden = !(activePair && activePair.group.kind === "similars");

    const groupListEl = document.getElementById("mockupGroupList");
    if (groupListEl) {
      groupListEl.innerHTML = !visibleGroups.length
        ? `<div style="padding:20px 14px;font-size:12px;color:#8E8E93;">${md.emptySelected}</div>`
        : visibleGroups.map((g) => {
            const groupMb = g.photos.reduce((s, p) => s + p.sizeMb, 0);
            const isActive = activePair && activePair.group.id === g.id;
            const badge = g.kind === "similars"
              ? `<span class="mac-group-badge is-ai">✦ ${fmtNum(g.bestScore, 1)}</span>`
              : `<span class="mac-group-badge is-keep">✓ ${md.keepShort}</span>`;
            return `<button type="button" class="mac-group-item ${isActive ? "is-active" : ""}" data-select-group="${g.id}">
              <div class="mac-group-thumb">${renderSceneSvg(g.thumbScene)}</div>
              <div class="mac-group-info">
                <div class="mac-group-name-row"><span class="mac-group-name">${g.title}</span><span class="mac-group-size">${fmtMb(groupMb)}</span></div>
                <div class="mac-group-sub-row"><span>${g.photos.length} ${md.photosUnit}</span>${badge}</div>
              </div>
            </button>`;
          }).join("");
    }

    const metaEl = document.getElementById("mockupPhotoMeta");
    const stageEl = document.getElementById("mockupStage");

    if (!activePair) {
      if (metaEl) metaEl.innerHTML = "";
      if (stageEl) stageEl.innerHTML = `<div style="margin:auto;text-align:center;color:#8E8E93;font-size:13px;">${md.emptySelected}</div>`;
    } else {
      const { group, photo } = activePair;
      const isSim = group.kind === "similars";
      const renderTagPills = (tags) => (tags || []).map((t) => {
        const cls = t.tone === "positive" ? "mac-pill-positive" : t.tone === "warn" ? "mac-pill-warn" : "mac-pill-amber";
        return `<span class="mac-pill ${cls}">${t.tone === "positive" ? "✓ " : "⚠ "}${formatTagLabel(t, md)}</span>`;
      }).join("");

      const badgesHtml = !isSim
        ? (photo.isKeep
            ? `<span class="mac-pill mac-pill-keep">${md.recommendedKeepLargest}</span>`
            : `<span class="mac-pill mac-pill-tech">${photo.selected ? md.selectedForTrash : md.keepingClickToSelect}</span>`)
        : `<span class="mac-pill mac-pill-ai">✦ ${fmtNum(photo.aesthetic, 1)} / 100</span>
           <span class="mac-pill mac-pill-tech">★ ${md.techLabel} ${fmtNum(photo.tech, 1)}</span>${renderTagPills(photo.tags)}`;

      if (metaEl) {
        metaEl.innerHTML = `<div class="mac-meta-file"><div class="mac-meta-filename">${photo.name}</div><div class="mac-meta-specs">${fmtMb(photo.sizeMb)} • ${photo.dims}</div></div><div class="mac-meta-badges">${badgesHtml}</div>`;
      }

      if (stageEl) {
        const checkSvg = `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#FFF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;
        if (mockupState.viewMode === "single") {
          const overlayScore = isSim ? `<div class="mac-overlay-score">✦ ${fmtNum(photo.aesthetic, 1)} / 100</div>` : "";
          const filmstrip = group.photos.map((p) => {
            const cls = [p.id === photo.id ? "is-focused" : "", p.isKeep ? "is-keep-best" : "", p.selected ? "is-selected-trash" : ""].filter(Boolean).join(" ");
            const sub = !isSim
              ? (p.isKeep ? `${fmtMb(p.sizeMb)} • ✓ ${md.keepShort}` : fmtMb(p.sizeMb))
              : `✦ ${fmtNum(p.aesthetic, 1)} • ${p.tags && p.tags[0] ? formatTagLabel(p.tags[0], md) : ""}`;
            return `<button type="button" class="mac-film-card ${cls}" data-select-photo="${p.id}">
              <div class="mac-film-thumb">${renderSceneSvg(p.scene)}</div>
              <div class="mac-film-meta"><div class="mac-film-title">${p.name}</div><div class="mac-film-sub">${sub}</div></div>
            </button>`;
          }).join("");

          stageEl.innerHTML = `<div class="mac-single-canvas-wrap">
            <button type="button" class="mac-select-toggle ${photo.selected ? "is-selected" : ""}" data-toggle-trash="${photo.id}">
              <span class="mac-checkbox-box">${photo.selected ? checkSvg : ""}</span>
              <span>${photo.selected ? md.selectedForTrash : md.keepingClickToSelect}</span>
            </button>${overlayScore}
            <div class="mac-canvas-art">${renderSceneSvg(photo.scene)}</div>
          </div><div class="mac-filmstrip">${filmstrip}</div>`;
        } else {
          const cards = group.photos.map((p) => {
            const cls = [p.isKeep ? "is-keep-best" : "", p.selected ? "is-selected-trash" : ""].filter(Boolean).join(" ");
            const detail = !isSim
              ? (p.isKeep ? `<span class="mac-pill mac-pill-keep" style="align-self:flex-start;">${md.recommendedKeepLargest}</span>` : `<span class="mac-pill mac-pill-tech" style="align-self:flex-start;">${fmtMb(p.sizeMb)}</span>`)
              : `<div style="display:flex;flex-wrap:wrap;gap:5px;"><span class="mac-pill mac-pill-ai">✦ ${fmtNum(p.aesthetic, 1)}</span>${renderTagPills(p.tags)}</div>
                 <div class="mac-metric-bars">
                   <div class="mac-bar-row"><span class="mac-bar-label">${md.compBarLabel}</span><div class="mac-bar-track"><div class="mac-bar-fill" style="width:${p.compBar}%;background:#5E5CE6;"></div></div></div>
                   ${p.faceBar !== null ? `<div class="mac-bar-row"><span class="mac-bar-label">${md.faceBarLabel}</span><div class="mac-bar-track"><div class="mac-bar-fill" style="width:${p.faceBar}%;background:${p.closedEyes ? "#FF453A" : "#30D158"};"></div></div></div>` : ""}
                 </div>`;
            return `<div class="mac-compare-card ${cls}" data-toggle-trash="${p.id}">
              <div class="mac-compare-art">${renderSceneSvg(p.scene)}</div>
              <div class="mac-compare-head"><span class="mac-compare-name">${p.name}</span><span class="mac-checkbox-box">${p.selected ? checkSvg : ""}</span></div>
              <div style="font-size:11px;color:#8E8E93;">${fmtMb(p.sizeMb)} • ${p.dims}</div>${detail}
            </div>`;
          }).join("");
          stageEl.innerHTML = `<div class="mac-compare-grid">${cards}</div>`;
        }
      }
    }

    const footerSummaryEl = document.getElementById("mockupFooterSummary");
    const trashBtnLabelEl = document.getElementById("mockupTrashBtnLabel");
    if (footerSummaryEl) footerSummaryEl.textContent = `${md.footerTotalPrefix}: ${fmtMb(totalBytesMb)} • ${totalPhotos} ${md.photosUnit}`;
    if (trashBtnLabelEl) trashBtnLabelEl.textContent = `${md.moveToTrashPrefix} (${fmtMb(selectedBytesMb)})`;
  }

  function applyVisitorOsHighlight() {
    const isWin = typeof navigator !== "undefined" && typeof navigator.userAgent === "string" && navigator.userAgent.includes("Win");
    if (!isWin) return;
    const heroActions = document.getElementById("heroActions");
    const dmgBtn = heroActions ? heroActions.querySelector("[data-download-dmg]") : null;
    const winBtn = heroActions ? heroActions.querySelector("[data-download-win]") : null;
    if (dmgBtn && winBtn) {
      dmgBtn.classList.remove("btn-primary");
      dmgBtn.classList.add("btn-secondary");
      winBtn.classList.remove("btn-secondary");
      winBtn.classList.add("btn-primary");
      heroActions.insertBefore(winBtn, dmgBtn);
    }
    const navBtn = document.querySelector(".site-nav [data-nav-download]");
    if (navBtn) {
      navBtn.removeAttribute("data-download-dmg");
      navBtn.setAttribute("data-download-win", "");
      const navIcon = navBtn.querySelector("svg");
      if (navIcon) {
        navIcon.innerHTML = '<rect x="3" y="3" width="8.2" height="8.2" rx="1.2"/><rect x="12.8" y="3" width="8.2" height="8.2" rx="1.2"/><rect x="3" y="12.8" width="8.2" height="8.2" rx="1.2"/><rect x="12.8" y="12.8" width="8.2" height="8.2" rx="1.2"/>';
      }
    }
  }

  function renderDownloadCount() {
    const wrap = document.getElementById("heroDownloadsWrap");
    const textEl = document.getElementById("heroDownloadsText");
    if (!wrap || !textEl) return;
    if (releaseState.downloadCount > 0) {
      const formatted = releaseState.downloadCount.toLocaleString(currentLang === "vi" ? "vi-VN" : "en-US");
      textEl.textContent = `${formatted} ${I18N[currentLang].hero.downloadsUnit}`;
      wrap.hidden = false;
    } else {
      wrap.hidden = true;
    }
  }

  function applyReleaseStateToDom() {
    document.querySelectorAll("[data-download-dmg]").forEach((el) => el.setAttribute("href", releaseState.dmgUrl));
    document.querySelectorAll("[data-download-zip]").forEach((el) => el.setAttribute("href", releaseState.zipUrl));
    document.querySelectorAll("[data-download-win]").forEach((el) => {
      el.setAttribute("href", releaseState.winUrl);
      el.setAttribute("title", `Windows 10/11 (x64) • ${releaseState.winSizeLabel}`);
    });
    document.querySelectorAll("[data-github-link]").forEach((el) => el.setAttribute("href", releaseState.githubUrl));
    document.querySelectorAll("[data-release-version]").forEach((el) => { el.textContent = releaseState.version; });
    renderDownloadCount();
  }

  async function resolveLatestGitHubRelease() {
    if (!SITE_CONFIG.autoFetchLatestRelease || !SITE_CONFIG.githubRepo) return;
    try {
      const res = await fetch(`https://api.github.com/repos/${SITE_CONFIG.githubRepo}/releases/latest`, {
        headers: { Accept: "application/vnd.github+json" },
      });
      if (!res.ok) return;
      const release = await res.json();
      if (release && typeof release.tag_name === "string" && release.tag_name.trim()) {
        const tag = release.tag_name.trim();
        releaseState.version = tag.startsWith("v") ? tag : `v${tag}`;
      }
      if (release && Array.isArray(release.assets)) {
        const dmg = release.assets.find((a) => a && typeof a.name === "string" && a.name.toLowerCase().endsWith(".dmg"));
        const zip = release.assets.find((a) => a && typeof a.name === "string" && a.name.toLowerCase().endsWith(".zip"));
        const win =
          release.assets.find((a) => a && typeof a.name === "string" && /\.exe$/i.test(a.name)) ||
          release.assets.find((a) => a && typeof a.name === "string" && /\.(exe|msi)$/i.test(a.name));
        if (dmg && dmg.browser_download_url) releaseState.dmgUrl = dmg.browser_download_url;
        if (zip && zip.browser_download_url) releaseState.zipUrl = zip.browser_download_url;
        if (win && win.browser_download_url) {
          releaseState.winUrl = win.browser_download_url;
          if (typeof win.size === "number" && win.size > 0) {
            releaseState.winSizeLabel = `~${Math.max(1, Math.round(win.size / (1024 * 1024)))} MB`;
          }
        }
        const totalDownloads = release.assets.reduce(
          (sum, a) => sum + (a && typeof a.download_count === "number" ? a.download_count : 0),
          0
        );
        if (totalDownloads > 0) releaseState.downloadCount = totalDownloads;
      }
      applyReleaseStateToDom();
    } catch {}
  }

  async function copyTextSafe(text) {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      try { await navigator.clipboard.writeText(text); return true; } catch {}
    }
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.cssText = "position:fixed;top:-9999px;opacity:0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch { return false; }
  }

  function bindEvents() {
    document.querySelectorAll("[data-lang-btn]").forEach((btn) => {
      btn.addEventListener("click", () => applyLanguage(btn.getAttribute("data-lang-btn")));
    });

    document.querySelectorAll("[data-mockup-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        mockupState.tab = btn.getAttribute("data-mockup-tab");
        const visible = getFilteredGroups();
        if (visible.length) {
          mockupState.activeGroupId = visible[0].id;
          mockupState.activePhotoId = visible[0].photos[0].id;
        }
        renderMockup();
      });
    });

    const winEl = document.getElementById("mockupWindow");
    const collapseBtn = document.getElementById("mockupSidebarToggle");
    const expandBtn = document.getElementById("mockupSidebarExpand");
    if (winEl && collapseBtn) collapseBtn.addEventListener("click", () => winEl.classList.add("is-sidebar-collapsed"));
    if (winEl && expandBtn) expandBtn.addEventListener("click", () => winEl.classList.remove("is-sidebar-collapsed"));

    document.querySelectorAll("[data-mockup-view]").forEach((btn) => {
      btn.addEventListener("click", () => {
        mockupState.viewMode = btn.getAttribute("data-mockup-view");
        renderMockup();
      });
    });

    if (winEl) {
      winEl.addEventListener("click", (e) => {
        const groupBtn = e.target.closest("[data-select-group]");
        if (groupBtn) {
          const found = mockupState.groups.find((g) => g.id === groupBtn.getAttribute("data-select-group"));
          if (found) { mockupState.activeGroupId = found.id; mockupState.activePhotoId = found.photos[0].id; renderMockup(); }
          return;
        }
        const photoBtn = e.target.closest("[data-select-photo]");
        if (photoBtn) {
          mockupState.activePhotoId = photoBtn.getAttribute("data-select-photo");
          renderMockup();
          return;
        }
        const toggleBtn = e.target.closest("[data-toggle-trash]");
        if (toggleBtn) {
          const pid = toggleBtn.getAttribute("data-toggle-trash");
          mockupState.groups.forEach((g) => g.photos.forEach((p) => {
            if (p.id === pid) { p.selected = !p.selected; mockupState.activePhotoId = p.id; }
          }));
          renderMockup();
        }
      });
    }

    const autoBtn = document.getElementById("mockupAutoSelectBtn");
    if (autoBtn) {
      autoBtn.addEventListener("click", () => {
        mockupState.groups.forEach((g) => g.photos.forEach((p) => { p.selected = !p.isKeep; }));
        renderMockup();
        showMockupToast(I18N[currentLang].mockupDynamic.toastAutoSelected);
      });
    }

    const aiBtn = document.getElementById("mockupAiScoreBtn");
    if (aiBtn) aiBtn.addEventListener("click", () => showMockupToast(I18N[currentLang].mockupDynamic.toastAiInfo));

    const trashBtn = document.getElementById("mockupTrashBtn");
    if (trashBtn) trashBtn.addEventListener("click", () => showMockupToast(I18N[currentLang].mockupDynamic.toastTrashDemo));

    const copyBtn = document.getElementById("copyXattrBtn");
    const copyLabel = document.getElementById("copyXattrLabel");
    const cmdEl = document.getElementById("xattrCmdText");
    let copyTimer = null;
    if (copyBtn && copyLabel && cmdEl) {
      copyBtn.addEventListener("click", async () => {
        if (!(await copyTextSafe(cmdEl.textContent.trim()))) return;
        copyBtn.classList.add("is-copied");
        copyLabel.textContent = I18N[currentLang].install.btnCopied;
        if (copyTimer) clearTimeout(copyTimer);
        copyTimer = setTimeout(() => {
          copyBtn.classList.remove("is-copied");
          copyLabel.textContent = I18N[currentLang].install.btnCopy;
        }, 2200);
      });
    }

    const revealEls = document.querySelectorAll(".reveal");
    if ("IntersectionObserver" in window) {
      const obs = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) { entry.target.classList.add("is-visible"); obs.unobserve(entry.target); }
        });
      }, { threshold: 0.08 });
      revealEls.forEach((el) => obs.observe(el));
    } else {
      revealEls.forEach((el) => el.classList.add("is-visible"));
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    applyVisitorOsHighlight();
    applyReleaseStateToDom();
    bindEvents();
    applyLanguage(currentLang);
    resolveLatestGitHubRelease();
  });
})();
