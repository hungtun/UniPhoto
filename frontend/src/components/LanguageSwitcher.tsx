import { useI18n } from "../i18n/I18nContext";

interface LanguageSwitcherProps {
  compact?: boolean;
}

export default function LanguageSwitcher({
  compact = false,
}: LanguageSwitcherProps) {
  const { lang, setLang, t } = useI18n();

  const paddingCls = compact
    ? "px-2 py-0.5 text-[11px]"
    : "px-2.5 py-1 text-[11.5px]";

  return (
    <div
      title={t.app.switchLangTooltip}
      className="bg-[#2C2C2E] border border-white/[0.06] inline-flex items-center rounded-[7px] p-[2px] shrink-0 select-none"
    >
      <button
        type="button"
        onClick={() => setLang("vi")}
        className={`${paddingCls} rounded-[5px] font-medium tracking-wide transition-colors cursor-pointer ${
          lang === "vi"
            ? "bg-[#48484A] text-white shadow-sm"
            : "text-[#98989D] hover:text-white"
        }`}
      >
        VI
      </button>
      <button
        type="button"
        onClick={() => setLang("en")}
        className={`${paddingCls} rounded-[5px] font-medium tracking-wide transition-colors cursor-pointer ${
          lang === "en"
            ? "bg-[#48484A] text-white shadow-sm"
            : "text-[#98989D] hover:text-white"
        }`}
      >
        EN
      </button>
    </div>
  );
}
