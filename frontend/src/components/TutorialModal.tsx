import { useCallback, useEffect, useState } from "react";
import { useI18n } from "../i18n/I18nContext";
import { formatQualityScore } from "../utils/photoHelpers";
import LanguageSwitcher from "./LanguageSwitcher";
import {
  IconCheckCircle,
  IconChevronLeft,
  IconChevronRight,
  IconDuplicates,
  IconFolder,
  IconGrid,
  IconSimilars,
  IconSingle,
  IconSparkles,
  IconTrash,
  IconWand,
  IconWarning,
} from "./MacIcons";

export const TUTORIAL_STORAGE_KEY = "uniphoto_tutorial_seen_v1";

const TOTAL_STEPS = 4;

export function hasSeenTutorial(): boolean {
  try {
    const val = localStorage.getItem(TUTORIAL_STORAGE_KEY);
    return val === "1" || val === "true";
  } catch {
    return false;
  }
}

export function markTutorialSeen(): void {
  try {
    localStorage.setItem(TUTORIAL_STORAGE_KEY, "1");
  } catch {
    // Ignore storage errors in restricted environments
  }
}

export interface TutorialModalProps {
  open: boolean;
  onClose: () => void;
}

export default function TutorialModal({ open, onClose }: TutorialModalProps) {
  const { lang, t, formatBytes, isWindows } = useI18n();
  const [stepIndex, setStepIndex] = useState<number>(0);

  useEffect(() => {
    if (open) {
      setStepIndex(0);
    }
  }, [open]);

  const handleDismiss = useCallback(() => {
    markTutorialSeen();
    onClose();
  }, [onClose]);

  const handlePrev = useCallback(() => {
    setStepIndex((prev) => (prev > 0 ? prev - 1 : prev));
  }, []);

  const handleNextOrFinish = useCallback(() => {
    if (stepIndex < TOTAL_STEPS - 1) {
      setStepIndex((prev) => Math.min(TOTAL_STEPS - 1, prev + 1));
    } else {
      handleDismiss();
    }
  }, [stepIndex, handleDismiss]);

  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        handleDismiss();
        return;
      }

      if (e.metaKey || e.ctrlKey || e.altKey) {
        return;
      }

      if (e.key === "ArrowRight") {
        e.preventDefault();
        e.stopPropagation();
        setStepIndex((prev) => (prev < TOTAL_STEPS - 1 ? prev + 1 : prev));
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        e.stopPropagation();
        setStepIndex((prev) => (prev > 0 ? prev - 1 : prev));
      } else if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        if (stepIndex < TOTAL_STEPS - 1) {
          setStepIndex((prev) => prev + 1);
        } else {
          handleDismiss();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [open, stepIndex, handleDismiss]);

  if (!open) return null;

  const steps = [
    {
      title: t.tutorial.step1Title,
      desc: t.tutorial.step1Desc,
      points: [
        t.tutorial.step1Point1,
        t.tutorial.step1Point2,
        t.tutorial.step1Point3,
      ],
    },
    {
      title: t.tutorial.step2Title,
      desc: t.tutorial.step2Desc,
      points: [
        t.tutorial.step2Point1,
        t.tutorial.step2Point2,
        t.tutorial.step2Point3,
      ],
    },
    {
      title: t.tutorial.step3Title,
      desc: t.tutorial.step3Desc,
      points: [
        t.tutorial.step3Point1,
        t.tutorial.step3Point2,
        t.tutorial.step3Point3,
      ],
    },
    {
      title: t.tutorial.step4Title,
      desc: t.tutorial.step4Desc,
      points: [
        t.tutorial.step4Point1,
        t.tutorial.step4Point2,
        t.tutorial.step4Point3,
      ],
    },
  ];

  const currentStep = steps[stepIndex] ?? steps[0];
  const isFinalStep = stepIndex === TOTAL_STEPS - 1;

  const renderIllustration = () => {
    if (stepIndex === 0) {
      return (
        <div className="space-y-2.5">
          <div className="bg-[#242426] border border-dashed border-[#0A84FF]/55 rounded-xl px-3.5 py-2.5 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-9 h-9 rounded-lg bg-[#0A84FF]/15 border border-[#0A84FF]/30 text-[#0A84FF] flex items-center justify-center shrink-0">
                <IconFolder className="w-[18px] h-[18px]" />
              </div>
              <div className="min-w-0">
                <p className="text-[12.5px] font-medium text-[#F2F2F7] truncate">
                  {t.home.pickFolderTitle}
                </p>
                <p className="text-[11px] text-[#8E8E93] font-mono truncate">
                  {t.tutorial.previewFolderSample}
                </p>
              </div>
            </div>
            <span className="text-[11px] font-medium bg-[#2C2C2E] border border-white/[0.08] text-[#E5E5EA] px-2.5 py-1 rounded-[6px] shrink-0">
              {t.results.btnOpenFinder}
            </span>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[10.5px] font-mono text-[#AEAEB2] bg-[#242426] border border-white/[0.06] px-2 py-0.5 rounded-md">
              .JPG • .PNG • .HEIC
            </span>
            <span className="inline-flex items-center gap-1 text-[10.5px] font-medium text-[#32D74B] bg-[#30D158]/15 border border-[#30D158]/30 px-2 py-0.5 rounded-md">
              <IconCheckCircle className="w-3 h-3" />
              <span>{t.tutorial.previewOfflineBadge}</span>
            </span>
          </div>
        </div>
      );
    }

    if (stepIndex === 1) {
      return (
        <div className="space-y-2.5">
          <div className="grid grid-cols-2 gap-2.5">
            <div className="bg-[#242426] border border-white/[0.07] rounded-lg p-2.5">
              <div className="flex items-center gap-1.5 text-[11.5px] font-medium text-[#F2F2F7]">
                <IconDuplicates className="w-3.5 h-3.5 text-[#0A84FF] shrink-0" />
                <span className="truncate">{t.results.navAllDuplicates}</span>
              </div>
              <div className="mt-2 flex items-center justify-between gap-1.5">
                <span className="text-[10.5px] text-[#8E8E93] tabular-nums">
                  {formatBytes(8_808_038)}
                </span>
                <span className="text-[9.5px] bg-[#30D158]/16 border border-[#30D158]/35 text-[#32D74B] px-1.5 py-0.5 rounded-[5px] font-medium">
                  {t.results.badgeKeepShort}
                </span>
              </div>
            </div>

            <div className="bg-[#242426] border border-white/[0.07] rounded-lg p-2.5">
              <div className="flex items-center gap-1.5 text-[11.5px] font-medium text-[#F2F2F7]">
                <IconSimilars className="w-3.5 h-3.5 text-[#5E5CE6] shrink-0" />
                <span className="truncate">{t.results.navAllSimilars}</span>
              </div>
              <div className="mt-2 flex items-center justify-between gap-1.5">
                <span className="text-[10.5px] text-[#AEAEB2] truncate">
                  {t.tutorial.previewBurstBadge}
                </span>
                <span className="text-[10px] font-mono bg-[#5E5CE6]/20 border border-[#5E5CE6]/35 text-[#BF5AF2] px-1.5 py-0.5 rounded-[5px]">
                  4×
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between gap-2 bg-[#242426] border border-white/[0.06] rounded-lg px-2.5 py-1.5">
            <div className="bg-[#2C2C2E] p-[2px] rounded-[6px] inline-flex items-center gap-0.5">
              <span className="rounded-[4px] px-2 py-0.5 text-[10.5px] text-[#98989D] inline-flex items-center gap-1">
                <IconSingle className="w-3 h-3" />
                <span>{t.results.viewSingle}</span>
              </span>
              <span className="rounded-[4px] px-2 py-0.5 text-[10.5px] bg-[#48484A] text-white font-medium inline-flex items-center gap-1">
                <IconGrid className="w-3 h-3" />
                <span>{t.results.viewGrid}</span>
              </span>
            </div>

            <div className="inline-flex items-center gap-1 shrink-0">
              <kbd className="px-1.5 py-0.5 rounded-[5px] bg-[#3A3A3C] border border-white/[0.10] text-[10px] font-mono font-medium text-white">
                1
              </kbd>
              <kbd className="px-1.5 py-0.5 rounded-[5px] bg-[#3A3A3C] border border-white/[0.10] text-[10px] font-mono font-medium text-white">
                2
              </kbd>
            </div>
          </div>
        </div>
      );
    }

    if (stepIndex === 2) {
      return (
        <div className="space-y-2.5">
          <div className="flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 bg-[#5E5CE6] text-white text-[11px] font-medium px-2.5 py-1 rounded-[6px]">
              <IconSparkles className="w-3.5 h-3.5" />
              <span>{t.results.btnScoreAesthetics}</span>
            </span>
            <span className="text-[10.5px] text-[#8E8E93] truncate">
              {t.results.navAllSimilars}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            <div className="bg-[#242426] border border-[#30D158]/45 rounded-lg p-2.5">
              <div className="flex items-center justify-between gap-1.5">
                <span className="text-[11.5px] font-semibold text-[#32D74B] tabular-nums">
                  ✦ {formatQualityScore(92.4, lang)}
                </span>
                <span className="text-[9.5px] bg-[#30D158]/16 border border-[#30D158]/35 text-[#32D74B] px-1.5 py-0.5 rounded-[5px] font-medium">
                  {t.results.badgeKeepShort}
                </span>
              </div>
              <div className="mt-1.5 inline-flex items-center gap-1 text-[10.5px] text-[#32D74B] truncate max-w-full">
                <IconCheckCircle className="w-3 h-3 shrink-0" />
                <span className="truncate">
                  {t.results.aestheticTags.eyes_open_sharp}
                </span>
              </div>
            </div>

            <div className="bg-[#242426] border border-white/[0.07] rounded-lg p-2.5">
              <div className="flex items-center justify-between gap-1.5">
                <span className="text-[11.5px] font-medium text-[#FFD60A] tabular-nums">
                  ✦ {formatQualityScore(61.8, lang)}
                </span>
                <span className="text-[10px] font-mono text-[#8E8E93]">
                  IMG_02
                </span>
              </div>
              <div className="mt-1.5 inline-flex items-center gap-1 text-[10.5px] text-[#FF6961] truncate max-w-full">
                <IconWarning className="w-3 h-3 shrink-0" />
                <span className="truncate">
                  {t.results.aestheticTags.eyes_closed}
                </span>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="space-y-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2 bg-[#242426] border border-white/[0.07] rounded-lg px-3 py-2">
          <span className="inline-flex items-center gap-1.5 text-[11.5px] font-medium text-[#E5E5EA]">
            <IconWand className="w-3.5 h-3.5 text-[#0A84FF]" />
            <span>{t.results.btnAutoSelect}</span>
          </span>

          <div className="inline-flex items-center gap-1 shrink-0">
            <kbd className="px-1.5 py-0.5 rounded-[5px] bg-[#3A3A3C] border border-white/[0.10] text-[10px] font-mono font-medium text-white">
              {isWindows ? "Ctrl+A" : "⌘A"}
            </kbd>
            <kbd className="px-1.5 py-0.5 rounded-[5px] bg-[#3A3A3C] border border-white/[0.10] text-[10px] font-mono font-medium text-white">
              Space
            </kbd>
            <kbd className="px-1.5 py-0.5 rounded-[5px] bg-[#3A3A3C] border border-white/[0.10] text-[10px] font-mono font-medium text-white">
              ← →
            </kbd>
          </div>
        </div>

        <div className="flex items-center justify-between gap-2.5 bg-[#242426] border border-white/[0.07] rounded-lg px-3 py-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <IconCheckCircle className="w-3.5 h-3.5 text-[#30D158] shrink-0" />
            <span className="text-[11px] text-[#D1D1D6] truncate">
              {t.tutorial.previewSafeTrashBadge}
            </span>
          </div>

          <span className="inline-flex items-center gap-1 bg-[#007AFF] text-white text-[10.5px] font-medium px-2.5 py-1 rounded-[6px] shrink-0">
            <IconTrash className="w-3 h-3" />
            <span>{t.tutorial.previewTrashTarget}</span>
          </span>
        </div>
      </div>
    );
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="tutorial-modal-title"
      aria-describedby="tutorial-modal-desc"
      onClick={handleDismiss}
      className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm flex items-center justify-center p-4 select-none"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-[#262629]/95 backdrop-blur-2xl max-w-[480px] w-full rounded-2xl p-5 border border-white/[0.12] shadow-2xl"
      >
        {/* Top Bar: Step Pill + LanguageSwitcher + Skip */}
        <div className="flex items-center justify-between gap-2">
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-[#0A84FF]/15 border border-[#0A84FF]/30 text-[11.5px] font-medium text-[#64D2FF] tabular-nums">
            {t.tutorial.badgeStep(stepIndex + 1, TOTAL_STEPS)}
          </span>

          <div className="flex items-center gap-1.5">
            <LanguageSwitcher compact />
            <button
              type="button"
              onClick={handleDismiss}
              className="text-[12px] text-[#8E8E93] hover:text-white px-2 py-1 rounded-md hover:bg-white/[0.07] transition-colors cursor-pointer"
            >
              {t.tutorial.btnSkip}
            </button>
          </div>
        </div>

        {/* Visual Illustration Banner */}
        <div className="bg-[#1C1C1E] border border-white/[0.07] rounded-xl p-4 mt-3.5 min-h-[116px] flex flex-col justify-center">
          {renderIllustration()}
        </div>

        {/* Step Content */}
        <h3
          id="tutorial-modal-title"
          className="text-[16px] font-semibold tracking-tight text-[#F2F2F7] mt-4"
        >
          {currentStep.title}
        </h3>

        <p
          id="tutorial-modal-desc"
          className="text-[12.5px] text-[#AEAEB2] leading-relaxed mt-1.5"
        >
          {currentStep.desc}
        </p>

        <ul className="mt-3 space-y-1.5 text-[12px] text-[#D1D1D6]">
          {currentStep.points.map((point, idx) => (
            <li key={idx} className="flex items-start gap-2 leading-snug">
              <IconCheckCircle className="w-[14px] h-[14px] text-[#30D158] shrink-0 mt-[2px]" />
              <span>{point}</span>
            </li>
          ))}
        </ul>

        {/* Bottom Navigation Bar */}
        <div className="mt-5 pt-3.5 border-t border-white/[0.08] flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            {Array.from({ length: TOTAL_STEPS }).map((_, idx) => {
              const isActive = idx === stepIndex;
              return (
                <button
                  key={idx}
                  type="button"
                  aria-label={t.tutorial.stepDotAria(idx + 1)}
                  aria-current={isActive ? "step" : undefined}
                  onClick={() => setStepIndex(idx)}
                  className={`h-1.5 rounded-full transition-all cursor-pointer ${
                    isActive
                      ? "w-5 bg-[#0A84FF]"
                      : "w-1.5 bg-white/20 hover:bg-white/40"
                  }`}
                />
              );
            })}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {!isFinalStep && (
              <button
                type="button"
                onClick={handleDismiss}
                className="text-[12px] font-medium text-[#8E8E93] hover:text-[#F2F2F7] px-2.5 py-1.5 rounded-[7px] hover:bg-white/[0.06] transition-colors cursor-pointer"
              >
                {t.tutorial.btnSkip}
              </button>
            )}

            <button
              type="button"
              disabled={stepIndex === 0}
              onClick={handlePrev}
              className="bg-[#3A3A3C] hover:bg-[#48484A] disabled:opacity-35 disabled:pointer-events-none px-3 py-1.5 rounded-[7px] text-[12.5px] font-medium text-[#F2F2F7] inline-flex items-center gap-1 transition-colors cursor-pointer"
            >
              <IconChevronLeft className="w-[13px] h-[13px]" />
              <span>{t.tutorial.btnPrev}</span>
            </button>

            <button
              type="button"
              onClick={handleNextOrFinish}
              className="bg-[#007AFF] hover:bg-[#0071EB] text-white px-3.5 py-1.5 rounded-[7px] text-[12.5px] font-medium inline-flex items-center gap-1 transition-colors shadow-xs cursor-pointer"
            >
              <span>
                {isFinalStep ? t.tutorial.btnFinish : t.tutorial.btnNext}
              </span>
              {!isFinalStep && (
                <IconChevronRight className="w-[13px] h-[13px]" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
