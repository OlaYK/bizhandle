import { cn } from "../../lib/cn";

type LogoTone = "default" | "light" | "auth";
type LogoSize = "sm" | "md" | "lg";

const sizeMap: Record<LogoSize, { icon: string; title: string; subtitle: string }> = {
  sm: {
    icon: "h-8 w-8",
    title: "text-xl",
    subtitle: "text-[10px]"
  },
  md: {
    icon: "h-10 w-10",
    title: "text-2xl",
    subtitle: "text-xs"
  },
  lg: {
    icon: "h-12 w-12",
    title: "text-3xl",
    subtitle: "text-sm"
  }
};

interface MoniDeskLogoProps {
  className?: string;
  tone?: LogoTone;
  size?: LogoSize;
  showTagline?: boolean;
}

export function MoniDeskLogo({
  className,
  tone = "default",
  size = "md",
  showTagline = true
}: MoniDeskLogoProps) {
  const palette =
    tone === "light"
      ? {
          moni: "text-mint-100",
          desk: "text-cobalt-100",
          subtitle: "text-surface-200",
          iconStroke: "#d2f9df",
          iconFill: "url(#logoBubbleLight)"
        }
      : tone === "auth"
        ? {
            moni: "text-black",
            desk: "text-black",
            subtitle: "text-black",
            iconStroke: "#0f5e30",
            iconFill: "url(#logoBubbleDark)"
          }
      : {
          moni: "text-mint-700",
          desk: "text-surface-800",
          subtitle: "text-surface-500",
          iconStroke: "#0f5e30",
          iconFill: "url(#logoBubbleDark)"
        };

  return (
    <div className={cn("group inline-flex items-center gap-3", className)}>
      <svg
        viewBox="0 0 64 64"
        role="img"
        aria-label="MoniDesk Logo Icon"
        className={cn(
          "shrink-0 drop-shadow-sm transition-transform duration-300 group-hover:scale-105 group-hover:-rotate-1",
          sizeMap[size].icon
        )}
      >
        <defs>
          <linearGradient id="logoBubbleDark" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#27c25c" />
            <stop offset="100%" stopColor="#14823f" />
          </linearGradient>
          <linearGradient id="logoBubbleLight" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#7fe79d" />
            <stop offset="100%" stopColor="#27c25c" />
          </linearGradient>
          <linearGradient id="logoArrow" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#ffe052" />
            <stop offset="100%" stopColor="#f8c20d" />
          </linearGradient>
        </defs>

        <path
          d="M13 14h28c6.6 0 12 5.4 12 12v16c0 6.6-5.4 12-12 12H24L12 62V50c-6.1-.5-11-5.7-11-12V26c0-6.6 5.4-12 12-12z"
          fill={palette.iconFill}
          stroke={palette.iconStroke}
          strokeWidth="1.3"
        />
        <rect x="18" y="35" width="4" height="10" rx="1.2" fill="#0f2238" opacity="0.75" />
        <rect x="26" y="31" width="4" height="14" rx="1.2" fill="#0f2238" opacity="0.75" />
        <rect x="34" y="26" width="4" height="19" rx="1.2" fill="#0f2238" opacity="0.75" />
        <path
          d="M14 30c10-1 17-5 26-13l5 3-1 9-3-3c-9 9-16 13-30 16z"
          fill="url(#logoArrow)"
          className="animate-pulse-glow"
        />
      </svg>

      <div>
        <p className={cn("font-heading font-black leading-none tracking-tight", sizeMap[size].title)}>
          <span className={palette.moni}>Moni</span>
          <span className={palette.desk}>Desk</span>
        </p>
        {showTagline ? (
          <p className={cn("mt-0.5 font-medium uppercase tracking-[0.14em]", sizeMap[size].subtitle, palette.subtitle)}>
            Finance Command Center
          </p>
        ) : null}
      </div>
    </div>
  );
}
