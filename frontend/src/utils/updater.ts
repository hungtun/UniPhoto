import { getVersion } from "@tauri-apps/api/app";
import { openUrl } from "@tauri-apps/plugin-opener";
import { isWindowsPlatform } from "./platform";

export const GITHUB_REPO = "hungtun/UniPhoto";
export const FALLBACK_APP_VERSION = "0.2.0";

const LATEST_RELEASE_API_URL = `https://api.github.com/repos/${GITHUB_REPO}/releases/latest`;
const FALLBACK_RELEASES_PAGE_URL = `https://github.com/${GITHUB_REPO}/releases/latest`;
const UPDATE_CACHE_TTL_MS = 15 * 60 * 1000;
const FETCH_TIMEOUT_MS = 5000;

export interface ReleaseAssetInfo {
  name?: string;
  browser_download_url?: string;
  size?: number;
}

export interface UpdateInfo {
  currentVersion: string;
  latestVersion: string;
  hasUpdate: boolean;
  downloadUrl: string;
  releasePageUrl: string;
  assetName: string | null;
  assetSizeBytes: number | null;
  releaseNotes: string;
  publishedAt: string | null;
}

export type UpdateCheckStatus = "update_available" | "up_to_date" | "error";

export interface UpdateCheckResult {
  status: UpdateCheckStatus;
  info: UpdateInfo | null;
  currentVersion: string;
}

interface GitHubLatestReleasePayload {
  tag_name?: unknown;
  html_url?: unknown;
  body?: unknown;
  published_at?: unknown;
  draft?: unknown;
  assets?: unknown;
}

interface CachedUpdateEntry {
  timestamp: number;
  result: UpdateCheckResult;
}

const updateCheckCache = new Map<boolean, CachedUpdateEntry>();

export function parseSemver(raw: string): {
  major: number;
  minor: number;
  patch: number;
  prerelease: string;
} | null {
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim().replace(/^[vV]/, "");
  if (!trimmed) return null;

  const plusIdx = trimmed.indexOf("+");
  const withoutBuild = plusIdx >= 0 ? trimmed.slice(0, plusIdx) : trimmed;
  if (plusIdx >= 0 && !trimmed.slice(plusIdx + 1).trim()) {
    return null;
  }

  const dashIdx = withoutBuild.indexOf("-");
  const corePart = dashIdx >= 0 ? withoutBuild.slice(0, dashIdx) : withoutBuild;
  const prerelease =
    dashIdx >= 0 ? withoutBuild.slice(dashIdx + 1).trim() : "";
  if (dashIdx >= 0 && !prerelease) {
    return null;
  }

  const parts = corePart.split(".");
  if (parts.length !== 3) return null;
  if (!parts.every((part) => /^\d+$/.test(part))) return null;

  const major = Number(parts[0]);
  const minor = Number(parts[1]);
  const patch = Number(parts[2]);
  if (
    !Number.isSafeInteger(major) ||
    !Number.isSafeInteger(minor) ||
    !Number.isSafeInteger(patch) ||
    major < 0 ||
    minor < 0 ||
    patch < 0
  ) {
    return null;
  }

  return { major, minor, patch, prerelease };
}

function comparePrereleaseIdentifiers(a: string, b: string): number {
  const partsA = a.split(".");
  const partsB = b.split(".");
  const len = Math.min(partsA.length, partsB.length);

  for (let i = 0; i < len; i += 1) {
    const idA = partsA[i];
    const idB = partsB[i];
    if (idA === idB) continue;

    const numA = /^\d+$/.test(idA);
    const numB = /^\d+$/.test(idB);
    if (numA && numB) {
      const diff = Number(idA) - Number(idB);
      if (diff !== 0) return diff;
    } else if (numA && !numB) {
      return -1;
    } else if (!numA && numB) {
      return 1;
    } else {
      return idA < idB ? -1 : 1;
    }
  }

  return partsA.length - partsB.length;
}

export function isNewerSemver(latest: string, current: string): boolean {
  const parsedLatest = parseSemver(latest);
  const parsedCurrent = parseSemver(current);
  if (!parsedLatest || !parsedCurrent) return false;

  if (parsedLatest.major !== parsedCurrent.major) {
    return parsedLatest.major > parsedCurrent.major;
  }
  if (parsedLatest.minor !== parsedCurrent.minor) {
    return parsedLatest.minor > parsedCurrent.minor;
  }
  if (parsedLatest.patch !== parsedCurrent.patch) {
    return parsedLatest.patch > parsedCurrent.patch;
  }

  const latPre = parsedLatest.prerelease;
  const curPre = parsedCurrent.prerelease;
  if (!latPre && !curPre) return false;
  if (!latPre && curPre) return true;
  if (latPre && !curPre) return false;

  return comparePrereleaseIdentifiers(latPre, curPre) > 0;
}

function isWindowsAssetName(lowerName: string): boolean {
  if (lowerName.includes("x64-setup")) return true;
  // Match "win" (e.g. win, win32, win64, windows) without matching macOS "darwin"
  const withoutDarwin = lowerName.replace(/darwin/g, "");
  return withoutDarwin.includes("win");
}

export function selectPlatformReleaseAsset(
  assets: ReleaseAssetInfo[],
  isWindows: boolean
): { url: string; name: string; sizeBytes: number | null } | null {
  if (!Array.isArray(assets) || assets.length === 0) return null;

  const validAssets = assets.filter(
    (a): a is Required<Pick<ReleaseAssetInfo, "name" | "browser_download_url">> &
      ReleaseAssetInfo =>
      Boolean(
        a &&
          typeof a.name === "string" &&
          a.name.trim().length > 0 &&
          typeof a.browser_download_url === "string" &&
          a.browser_download_url.trim().length > 0
      )
  );

  if (validAssets.length === 0) return null;

  const formatSelected = (
    asset: Required<Pick<ReleaseAssetInfo, "name" | "browser_download_url">> &
      ReleaseAssetInfo
  ) => ({
    url: asset.browser_download_url.trim(),
    name: asset.name.trim(),
    sizeBytes:
      typeof asset.size === "number" &&
      Number.isFinite(asset.size) &&
      asset.size > 0
        ? asset.size
        : null,
  });

  if (isWindows) {
    const setupExe = validAssets.find((a) => {
      const lower = a.name.trim().toLowerCase();
      return lower.endsWith(".exe") && lower.includes("setup");
    });
    if (setupExe) return formatSelected(setupExe);

    const anyExe = validAssets.find((a) =>
      a.name.trim().toLowerCase().endsWith(".exe")
    );
    if (anyExe) return formatSelected(anyExe);

    const anyMsi = validAssets.find((a) =>
      a.name.trim().toLowerCase().endsWith(".msi")
    );
    if (anyMsi) return formatSelected(anyMsi);

    return null;
  }

  const macCandidates = validAssets.filter(
    (a) => !isWindowsAssetName(a.name.trim().toLowerCase())
  );

  const dmgAssets = macCandidates.filter((a) =>
    a.name.trim().toLowerCase().endsWith(".dmg")
  );
  if (dmgAssets.length > 0) {
    const preferredDmg =
      dmgAssets.find((a) =>
        /(aarch64|arm64|universal)/i.test(a.name.trim())
      ) ?? dmgAssets[0];
    return formatSelected(preferredDmg);
  }

  const zipAssets = macCandidates.filter((a) =>
    a.name.trim().toLowerCase().endsWith(".zip")
  );
  if (zipAssets.length > 0) {
    const preferredZip =
      zipAssets.find((a) =>
        /(aarch64|arm64|universal|macos|darwin)/i.test(a.name.trim())
      ) ?? zipAssets[0];
    return formatSelected(preferredZip);
  }

  return null;
}

export async function resolveCurrentAppVersion(): Promise<string> {
  try {
    const version = await getVersion();
    if (typeof version === "string" && parseSemver(version)) {
      return version.trim().replace(/^[vV]/, "");
    }
  } catch {
    // Fallback outside Tauri runtime
  }
  return FALLBACK_APP_VERSION;
}

export async function checkForAppUpdate(options?: {
  force?: boolean;
  isWindows?: boolean;
}): Promise<UpdateCheckResult> {
  const isWin =
    options?.isWindows !== undefined
      ? Boolean(options.isWindows)
      : isWindowsPlatform();
  const currentVersion = await resolveCurrentAppVersion();

  if (!options?.force) {
    const cached = updateCheckCache.get(isWin);
    if (
      cached &&
      Date.now() - cached.timestamp < UPDATE_CACHE_TTL_MS &&
      cached.result.status !== "error" &&
      cached.result.currentVersion === currentVersion
    ) {
      return cached.result;
    }
  }

  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => {
    controller.abort();
  }, FETCH_TIMEOUT_MS);

  try {
    const res = await fetch(LATEST_RELEASE_API_URL, {
      method: "GET",
      headers: {
        Accept: "application/vnd.github+json",
      },
      signal: controller.signal,
    });

    if (res.status === 404) {
      const noReleaseResult: UpdateCheckResult = {
        status: "up_to_date",
        info: null,
        currentVersion,
      };
      updateCheckCache.set(isWin, {
        timestamp: Date.now(),
        result: noReleaseResult,
      });
      return noReleaseResult;
    }

    if (!res.ok) {
      return {
        status: "error",
        info: null,
        currentVersion,
      };
    }

    const data = (await res.json()) as GitHubLatestReleasePayload;
    const rawTag =
      typeof data?.tag_name === "string" ? data.tag_name.trim() : "";
    if (!rawTag || !parseSemver(rawTag)) {
      return {
        status: "error",
        info: null,
        currentVersion,
      };
    }

    const latestVersion = rawTag.replace(/^[vV]/, "");
    const releasePageUrl =
      typeof data.html_url === "string" && data.html_url.trim().length > 0
        ? data.html_url.trim()
        : FALLBACK_RELEASES_PAGE_URL;

    const rawAssets: ReleaseAssetInfo[] = Array.isArray(data.assets)
      ? (data.assets as ReleaseAssetInfo[])
      : [];
    const selectedAsset = selectPlatformReleaseAsset(rawAssets, isWin);
    const downloadUrl =
      selectedAsset?.url ?? releasePageUrl ?? FALLBACK_RELEASES_PAGE_URL;
    const hasUpdate = isNewerSemver(rawTag, currentVersion);

    const info: UpdateInfo = {
      currentVersion,
      latestVersion,
      hasUpdate,
      downloadUrl,
      releasePageUrl,
      assetName: selectedAsset?.name ?? null,
      assetSizeBytes: selectedAsset?.sizeBytes ?? null,
      releaseNotes: typeof data.body === "string" ? data.body : "",
      publishedAt:
        typeof data.published_at === "string" && data.published_at.trim()
          ? data.published_at.trim()
          : null,
    };

    const result: UpdateCheckResult = {
      status: hasUpdate ? "update_available" : "up_to_date",
      info,
      currentVersion,
    };

    updateCheckCache.set(isWin, {
      timestamp: Date.now(),
      result,
    });

    return result;
  } catch {
    return {
      status: "error",
      info: null,
      currentVersion,
    };
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}

export async function openExternalReleaseUrl(url: string): Promise<void> {
  if (typeof url !== "string") return;
  const target = url.trim();
  if (!/^https?:\/\//i.test(target)) return;

  try {
    await openUrl(target);
    return;
  } catch {
    if (typeof window !== "undefined" && typeof window.open === "function") {
      window.open(target, "_blank", "noopener,noreferrer");
    }
  }
}
