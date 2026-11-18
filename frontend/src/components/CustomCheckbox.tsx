import React from "react";

interface CustomCheckboxProps {
  checked: boolean;
  onChange?: (e: React.MouseEvent) => void;
  size?: "sm" | "md";
}

export default function CustomCheckbox({
  checked,
  onChange,
  size = "md",
}: CustomCheckboxProps) {
  const sizeClasses =
    size === "sm"
      ? "w-4 h-4 rounded-[4.5px]"
      : "w-[17px] h-[17px] rounded-[5px]";
  const iconSize = size === "sm" ? "w-2.5 h-2.5" : "w-3 h-3";

  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      onClick={onChange}
      className={`${sizeClasses} shrink-0 flex items-center justify-center transition-colors duration-120 cursor-pointer select-none ${
        checked
          ? "bg-[#007AFF] border border-[#0A84FF] shadow-xs"
          : "bg-[#2C2C2E] hover:bg-[#3A3A3C] border border-white/[0.22] hover:border-white/[0.36]"
      }`}
    >
      <svg
        viewBox="0 0 12 12"
        fill="none"
        aria-hidden="true"
        className={`${iconSize} text-white transition-transform duration-120 ${
          checked ? "scale-100 opacity-100" : "scale-75 opacity-0"
        }`}
      >
        <path
          d="M2.2 6.2L4.8 8.8L9.8 3.2"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}
