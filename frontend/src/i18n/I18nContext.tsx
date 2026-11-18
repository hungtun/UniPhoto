import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import {
  Language,
  STORAGE_KEY,
  Translations,
  getInitialLanguage,
  translations,
} from "./translations";
import { formatGeminiBytes } from "../utils/photoHelpers";

interface I18nContextValue {
  lang: Language;
  setLang: (lang: Language) => void;
  toggleLang: () => void;
  t: Translations;
  formatBytes: (bytes: number) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Language>(getInitialLanguage);

  const setLang = useCallback((next: Language) => {
    setLangState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Ignore storage errors
    }
  }, []);

  const toggleLang = useCallback(() => {
    setLangState((prev) => {
      const next: Language = prev === "vi" ? "en" : "vi";
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        // Ignore storage errors
      }
      return next;
    });
  }, []);

  const t = translations[lang];

  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = t.app.windowTitle;
    try {
      getCurrentWindow()
        .setTitle(t.app.windowTitle)
        .catch(() => {});
    } catch {
      // Ignore when running outside Tauri runtime
    }
  }, [lang, t.app.windowTitle]);

  const formatBytes = useCallback(
    (bytes: number) => formatGeminiBytes(bytes, lang),
    [lang]
  );

  const value = useMemo<I18nContextValue>(
    () => ({
      lang,
      setLang,
      toggleLang,
      t,
      formatBytes,
    }),
    [lang, setLang, toggleLang, t, formatBytes]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return ctx;
}

