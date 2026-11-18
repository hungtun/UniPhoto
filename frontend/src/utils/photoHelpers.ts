import { PhotoItem } from "../api/PhotoApi";

export type ScreenMode = "home" | "scanning" | "results";
export type SidebarFilter = "duplicates" | "similars" | "selected";
export type ViewLayout = "single" | "grid";
export type SortMode = "size" | "count";
export type ScanStepKey =
  | "idle"
  | "resetting"
  | "scanning_dups"
  | "clustering_ai"
  | "scoring_aesthetics";

export type BestReasonKey =
  | "highest_res"
  | "sharpest"
  | "best_exposure"
  | "best_contrast"
  | "least_compressed"
  | "best_overall"
  | "eyes_open"
  | "level_camera"
  | "face_sharp"
  | "better_composition"
  | "best_aesthetics"
  | "largest_file"
  | "keep_default";

export interface UnifiedGroup {
  key: string;
  kind: "duplicates" | "similars";
  title: string;
  totalBytes: number;
  hasAestheticScores?: boolean;
  photos: PhotoItem[];
}

// Định dạng dung lượng theo ngôn ngữ (vi: dấu phẩy, en: dấu chấm)
export function formatGeminiBytes(
  bytes: number,
  lang: "vi" | "en" = "vi"
): string {
  if (!bytes || bytes <= 0) return "0 MB";
  const kb = bytes / 1024;
  if (kb < 1024) {
    return `${kb.toFixed(0)} KB`;
  }
  const formatDecimal = (val: string) =>
    lang === "vi" ? val.replace(".", ",") : val;

  const mb = bytes / (1024 * 1024);
  if (mb >= 1024) {
    return `${formatDecimal((mb / 1024).toFixed(2))} GB`;
  }
  return `${formatDecimal(mb.toFixed(1))} MB`;
}

export function formatQualityScore(
  score: number | null | undefined,
  lang: "vi" | "en" = "vi",
  decimals = 1
): string {
  if (score === null || score === undefined || Number.isNaN(score)) return "—";
  const raw = score.toFixed(decimals);
  return lang === "vi" ? raw.replace(".", ",") : raw;
}

export function getScoreToneClasses(score: number | null | undefined): string {
  const s = score ?? 0;
  if (s >= 75) {
    return "bg-[#30D158]/16 border-[#30D158]/40 text-[#30D158]";
  }
  if (s >= 55) {
    return "bg-[#0A84FF]/16 border-[#0A84FF]/40 text-[#64D2FF]";
  }
  return "bg-[#FFD60A]/16 border-[#FFD60A]/40 text-[#FFD60A]";
}

export function getAestheticScoreToneClasses(
  score: number | null | undefined
): string {
  const s = score ?? 0;
  if (s >= 74) {
    return "bg-[#30D158]/18 border-[#30D158]/40 text-[#32D74B]";
  }
  if (s >= 54) {
    return "bg-[#5E5CE6]/20 border-[#5E5CE6]/45 text-[#BF5AF2]";
  }
  if (s >= 40) {
    return "bg-[#FFD60A]/16 border-[#FFD60A]/40 text-[#FFD60A]";
  }
  return "bg-[#FF453A]/18 border-[#FF453A]/40 text-[#FF6961]";
}

const CRITICAL_WARNING_TAGS = new Set(["eyes_closed", "face_blurry"]);

const MODERATE_WARNING_TAGS = new Set(["tilted_horizon", "edge_subject"]);

const POSITIVE_EMERALD_TAGS = new Set(["eyes_open_sharp"]);
const POSITIVE_SKY_TAGS = new Set(["level_horizon", "rule_of_thirds"]);

export function isAestheticWarningTag(tag: string): boolean {
  return CRITICAL_WARNING_TAGS.has(tag) || MODERATE_WARNING_TAGS.has(tag);
}

export function getAestheticTagToneClasses(tag: string): string {
  if (CRITICAL_WARNING_TAGS.has(tag)) {
    return "bg-[#FF453A]/16 border-[#FF453A]/35 text-[#FF6961]";
  }
  if (MODERATE_WARNING_TAGS.has(tag)) {
    return "bg-[#FFD60A]/14 border-[#FFD60A]/35 text-[#FFD60A]";
  }
  if (POSITIVE_EMERALD_TAGS.has(tag)) {
    return "bg-[#30D158]/15 border-[#30D158]/35 text-[#32D74B]";
  }
  if (POSITIVE_SKY_TAGS.has(tag)) {
    return "bg-[#0A84FF]/15 border-[#0A84FF]/35 text-[#64D2FF]";
  }
  return "bg-[#2C2C2E] border-white/[0.10] text-[#E5E5EA]";
}

export function getBestPhotoReasonKey(
  best: PhotoItem,
  runnerUp?: PhotoItem,
  kind?: "duplicates" | "similars"
): BestReasonKey {
  const isScoredSimilar =
    kind === "similars" &&
    best.aesthetic_score !== null &&
    best.aesthetic_score !== undefined;

  if (isScoredSimilar) {
    if (!runnerUp) {
      return "best_aesthetics";
    }
    if (runnerUp.has_closed_eyes && !best.has_closed_eyes) {
      return "eyes_open";
    }
    if (
      runnerUp.aesthetic_tags?.includes("tilted_horizon") &&
      !best.aesthetic_tags?.includes("tilted_horizon")
    ) {
      return "level_camera";
    }
    if ((best.face_score ?? 0) - (runnerUp.face_score ?? 0) >= 6) {
      return "face_sharp";
    }
    if (
      (best.composition_score ?? 0) - (runnerUp.composition_score ?? 0) >=
      6
    ) {
      return "better_composition";
    }
    if ((best.sharpness_score ?? 0) - (runnerUp.sharpness_score ?? 0) >= 4) {
      return "sharpest";
    }
    return "best_aesthetics";
  }

  if (runnerUp && best.file_size > runnerUp.file_size) {
    return "largest_file";
  }

  return "keep_default";
}

export function getBaseTitle(fileName: string): string {
  const dotIdx = fileName.lastIndexOf(".");
  return dotIdx > 0 ? fileName.slice(0, dotIdx) : fileName;
}
