import { invoke } from "@tauri-apps/api/core";

export type DesktopPlatform = "macos" | "windows" | "linux";

let cachedIsWindows: boolean | null = null;

export function isWindowsPlatform(): boolean {
  if (cachedIsWindows !== null) {
    return cachedIsWindows;
  }
  if (typeof navigator !== "undefined") {
    const ua = navigator.userAgent || "";
    const plat = navigator.platform || "";
    if (/Windows/i.test(ua) || /^Win/i.test(plat)) {
      cachedIsWindows = true;
      return true;
    }
  }
  cachedIsWindows = false;
  return false;
}

export function applyPlatformDataset(isWindows: boolean): void {
  if (typeof document !== "undefined") {
    document.documentElement.dataset.platform = isWindows
      ? "windows"
      : "macos";
  }
}

export async function detectRuntimeIsWindows(): Promise<boolean> {
  const initial = isWindowsPlatform();
  applyPlatformDataset(initial);
  try {
    const os = await invoke<string>("get_platform");
    if (typeof os === "string" && os.trim().length > 0) {
      const isWin = os.trim().toLowerCase() === "windows";
      cachedIsWindows = isWin;
      applyPlatformDataset(isWin);
      return isWin;
    }
  } catch {
    // Fallback to navigator.userAgent outside Tauri runtime
  }
  return initial;
}
