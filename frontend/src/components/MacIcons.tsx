export interface MacIconProps {
  className?: string;
  size?: number;
  strokeWidth?: number;
}

export function IconSidebarLeft({
  className = "w-[16px] h-[16px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <rect x="2.5" y="3.5" width="15" height="13" rx="2.5" />
      <line x1="7.8" y1="3.5" x2="7.8" y2="16.5" />
      <line x1="4.7" y1="6.8" x2="6" y2="6.8" />
      <line x1="4.7" y1="9.3" x2="6" y2="9.3" />
      <line x1="4.7" y1="11.8" x2="6" y2="11.8" />
    </svg>
  );
}

export function IconDuplicates({
  className = "w-[16px] h-[16px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <rect x="6.5" y="6.5" width="10.5" height="10.5" rx="2.2" />
      <path d="M4.5 13.5H4.2A1.7 1.7 0 0 1 2.5 11.8V4.7A2.2 2.2 0 0 1 4.7 2.5h7.1a1.7 1.7 0 0 1 1.7 1.7v.3" />
    </svg>
  );
}

export function IconSimilars({
  className = "w-[16px] h-[16px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <rect x="2.5" y="5" width="12.5" height="11" rx="2.2" />
      <path d="M6 3h9.3A2.2 2.2 0 0 1 17.5 5.2v8.3" />
      <circle cx="6.5" cy="8.7" r="1.2" />
      <path d="M3.2 14.5l3.5-3.2 2.4 2.1 2.4-2 3.2 3.1" />
    </svg>
  );
}

export function IconCheckCircle({
  className = "w-[16px] h-[16px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <circle cx="10" cy="10" r="7.5" />
      <path d="M6.8 10.2l2.1 2.2 4.4-4.7" />
    </svg>
  );
}

export function IconFolder({
  className = "w-[16px] h-[16px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M2.5 5.8A2.1 2.1 0 0 1 4.6 3.7h3.2c.6 0 1.15.27 1.52.74l.95 1.21h5.13A2.1 2.1 0 0 1 17.5 7.75v6.95a2.1 2.1 0 0 1-2.1 2.1H4.6a2.1 2.1 0 0 1-2.1-2.1V5.8Z" />
    </svg>
  );
}

export function IconSparkles({
  className = "w-[16px] h-[16px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M9.5 2.5l1.35 4.05L14.9 7.9l-4.05 1.35L9.5 13.3 8.15 9.25 4.1 7.9l4.05-1.35L9.5 2.5Z" />
      <path d="M15.2 12.2l.65 1.95 1.95.65-1.95.65-.65 1.95-.65-1.95-1.95-.65 1.95-.65.65-1.95Z" />
    </svg>
  );
}

export function IconSearch({
  className = "w-[15px] h-[15px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <circle cx="8.8" cy="8.8" r="5.6" />
      <line x1="13" y1="13" x2="17" y2="17" />
    </svg>
  );
}

export function IconWand({
  className = "w-[15px] h-[15px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M3.2 16.8L13.5 6.5" />
      <path d="M11.3 4.3l4.4 4.4" />
      <path d="M14.8 2.5v2.4M13.6 3.7h2.4" />
      <path d="M6.2 3.2v1.8M5.3 4.1h1.8" />
      <path d="M16 11.2v1.8M15.1 12.1h1.8" />
    </svg>
  );
}

export function IconSort({
  className = "w-[15px] h-[15px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M6.5 4v12" />
      <path d="M3.8 6.8L6.5 4l2.7 2.8" />
      <path d="M13.5 16V4" />
      <path d="M10.8 13.2L13.5 16l2.7-2.8" />
    </svg>
  );
}

export function IconRefresh({
  className = "w-[15px] h-[15px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M16.2 6.8A6.5 6.5 0 1 0 16.5 11" />
      <polyline points="16.5 3.4 16.5 7 12.9 7" />
    </svg>
  );
}

export function IconEye({
  className = "w-[15px] h-[15px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M2.2 10s2.9-5.2 7.8-5.2 7.8 5.2 7.8 5.2-2.9 5.2-7.8 5.2S2.2 10 2.2 10Z" />
      <circle cx="10" cy="10" r="2.3" />
    </svg>
  );
}

export function IconFinder({
  className = "w-[15px] h-[15px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <rect x="2.8" y="3" width="14.4" height="14" rx="3" />
      <path d="M10.4 3c-.6 3.2-.9 5.7-.9 7.8h1.8c-.1 2.2.2 4.3.9 6.2" />
      <line x1="6.6" y1="7.5" x2="6.6" y2="8.8" />
      <line x1="13.6" y1="7.5" x2="13.6" y2="8.8" />
      <path d="M6.8 13.1c1 .9 2.2 1.3 3.4 1.3 1.2 0 2.3-.4 3.2-1.3" />
    </svg>
  );
}

export function IconGrid({
  className = "w-[15px] h-[15px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <rect x="3" y="3" width="5.8" height="5.8" rx="1.4" />
      <rect x="11.2" y="3" width="5.8" height="5.8" rx="1.4" />
      <rect x="3" y="11.2" width="5.8" height="5.8" rx="1.4" />
      <rect x="11.2" y="11.2" width="5.8" height="5.8" rx="1.4" />
    </svg>
  );
}

export function IconSingle({
  className = "w-[15px] h-[15px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <rect x="2.8" y="3.8" width="14.4" height="12.4" rx="2.2" />
      <circle cx="7.2" cy="8" r="1.3" />
      <path d="M3.4 14.5l4.2-3.9 2.9 2.6 2.7-2.2 3.6 3.5" />
    </svg>
  );
}

export function IconKeyboard({
  className = "w-[15px] h-[15px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <rect x="2.2" y="4.5" width="15.6" height="11" rx="2.2" />
      <line x1="5.4" y1="8" x2="6.2" y2="8" />
      <line x1="8.6" y1="8" x2="9.4" y2="8" />
      <line x1="11.8" y1="8" x2="12.6" y2="8" />
      <line x1="14.2" y1="8" x2="14.8" y2="8" />
      <line x1="5.4" y1="10.6" x2="6.4" y2="10.6" />
      <line x1="9" y1="10.6" x2="11" y2="10.6" />
      <line x1="13.6" y1="10.6" x2="14.6" y2="10.6" />
      <line x1="6.8" y1="13" x2="13.2" y2="13" />
    </svg>
  );
}

export function IconTrash({
  className = "w-[15px] h-[15px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M3.5 5.5h13" />
      <path d="M7.5 5.5V3.8a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1.7" />
      <path d="M5.2 5.5l.8 10.4a1.6 1.6 0 0 0 1.6 1.5h4.8a1.6 1.6 0 0 0 1.6-1.5l.8-10.4" />
      <line x1="8.5" y1="8.8" x2="8.5" y2="14" />
      <line x1="11.5" y1="8.8" x2="11.5" y2="14" />
    </svg>
  );
}

export function IconClose({
  className = "w-[14px] h-[14px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <line x1="5.2" y1="5.2" x2="14.8" y2="14.8" />
      <line x1="14.8" y1="5.2" x2="5.2" y2="14.8" />
    </svg>
  );
}

export function IconChevronLeft({
  className = "w-[14px] h-[14px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <polyline points="12.5 4.8 7.2 10 12.5 15.2" />
    </svg>
  );
}

export function IconChevronRight({
  className = "w-[14px] h-[14px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <polyline points="7.5 4.8 12.8 10 7.5 15.2" />
    </svg>
  );
}

export function IconChevronDown({
  className = "w-[14px] h-[14px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <polyline points="4.8 7.5 10 12.8 15.2 7.5" />
    </svg>
  );
}

export function IconPhotoStack({
  className = "w-[48px] h-[48px]",
  strokeWidth = 1.5,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <rect x="3" y="6.5" width="14.5" height="12.5" rx="2.5" />
      <path d="M7.5 4h11A2.5 2.5 0 0 1 21 6.5v9.5" />
      <circle cx="7.8" cy="11" r="1.4" />
      <path d="M3.8 17.2l4.2-3.8 2.8 2.4 2.8-2.3 3.4 3.7" />
    </svg>
  );
}

export function IconWarning({
  className = "w-[16px] h-[16px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M8.57 3.86L2.42 14.5A1.65 1.65 0 0 0 3.85 17h12.3a1.65 1.65 0 0 0 1.43-2.5L11.43 3.86a1.65 1.65 0 0 0-2.86 0Z" />
      <line x1="10" y1="8" x2="10" y2="11.6" />
      <circle cx="10" cy="14.2" r="0.6" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconArrowDownCircle({
  className = "w-[16px] h-[16px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <circle cx="10" cy="10" r="7.5" />
      <line x1="10" y1="6.5" x2="10" y2="13.2" />
      <polyline points="7.2 10.6 10 13.5 12.8 10.6" />
    </svg>
  );
}

export function IconQuestionCircle({
  className = "w-[15px] h-[15px]",
  strokeWidth = 1.7,
}: MacIconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <circle cx="10" cy="10" r="7.5" />
      <path d="M8.1 7.75a1.9 1.9 0 1 1 2.85 1.65c-.52.3-.95.7-.95 1.35v.25" />
      <circle cx="10" cy="13.9" r="0.65" fill="currentColor" stroke="none" />
    </svg>
  );
}
