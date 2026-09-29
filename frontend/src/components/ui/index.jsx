// Shared UI kit for the signed-in app.
// Every page composes these primitives so that layout, spacing, radii and
// typography stay consistent across tabs.

import { forwardRef } from "react";

const cx = (...parts) => parts.filter(Boolean).join(" ");

/* ── Layout ─────────────────────────────────────────────────────────── */

// Single content width for every signed-in page.
export function Page({ className = "", style, children }) {
  return (
    <div className={cx("w-full max-w-5xl mx-auto", className)} style={style}>
      {children}
    </div>
  );
}

export function Eyebrow({ className = "", children, tone = "muted" }) {
  return (
    <span
      className={cx(
        "block text-xs font-bold uppercase tracking-[0.1em]",
        tone === "primary" ? "text-[var(--primary)]" : "text-[var(--accent1)]",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  onBack,
  align = "start",
  className = "",
}) {
  const centered = align === "center";
  return (
    <header
      className={cx(
        "mb-10 flex gap-4",
        centered
          ? "flex-col items-center text-center"
          : "flex-col sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div className={cx("flex items-start gap-3 min-w-0", centered && "justify-center")}>
        {onBack && (
          <IconButton icon="arrow_back" onClick={onBack} label="Back" className="mt-1 -ml-2" />
        )}
        <div className="min-w-0">
          {eyebrow && <Eyebrow className="mb-2">{eyebrow}</Eyebrow>}
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[var(--dark)]">
            {title}
          </h1>
          {subtitle && (
            <p className={cx("mt-2 text-[var(--accent1)]", centered && "max-w-lg mx-auto")}>
              {subtitle}
            </p>
          )}
        </div>
      </div>
      {actions && <div className="flex items-center gap-3 shrink-0">{actions}</div>}
    </header>
  );
}

export function SectionTitle({ children, actions, className = "" }) {
  return (
    <div className={cx("flex items-center justify-between gap-4 mb-5", className)}>
      <h3 className="text-lg font-bold text-[var(--dark)]">{children}</h3>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ── Surfaces ───────────────────────────────────────────────────────── */

const CARD_VARIANT = {
  elevated: "bg-white shadow-[0_8px_32px_rgba(45,52,51,0.06)]",
  tonal: "bg-[var(--surface-container-low)]",
  outline: "bg-white border border-[rgba(172,179,178,0.25)]",
  primary: "bg-[var(--primary)] text-[var(--on-primary)]",
  accent: "bg-[var(--tertiary-container)]",
};

const CARD_PADDING = {
  none: "",
  sm: "p-4 sm:p-5",
  md: "p-6",
  lg: "p-6 sm:p-8",
};

export const Card = forwardRef(function Card(
  {
    variant = "elevated",
    padding = "lg",
    interactive = false,
    selected = false,
    className = "",
    as: Tag = "div",
    ...rest
  },
  ref,
) {
  return (
    <Tag
      ref={ref}
      className={cx(
        "rounded-3xl relative",
        CARD_VARIANT[variant],
        CARD_PADDING[padding],
        interactive &&
          "cursor-pointer transition-all hover:-translate-y-0.5 hover:shadow-[0_12px_32px_rgba(45,52,51,0.10)]",
        selected && "outline outline-2 outline-[var(--primary)]",
        className,
      )}
      {...rest}
    />
  );
});

const TILE_SIZE = {
  sm: "w-10 h-10 rounded-xl",
  md: "w-12 h-12 rounded-2xl",
  lg: "w-16 h-16 rounded-2xl",
};
const TILE_ICON = { sm: 20, md: 24, lg: 30 };

export function IconTile({ icon, size = "md", tone = "tonal", className = "", style }) {
  const bg =
    tone === "primary"
      ? { background: "var(--primary)", color: "var(--on-primary)" }
      : tone === "accent"
        ? { background: "var(--tertiary-container)", color: "var(--primary)" }
        : tone === "inverse"
          ? { background: "rgba(255,255,255,0.15)", color: "inherit" }
          : { background: "var(--surface-container-low)", color: "var(--primary)" };
  return (
    <div
      className={cx("flex items-center justify-center shrink-0", TILE_SIZE[size], className)}
      style={{ ...bg, ...style }}
    >
      <span className="material-symbols-outlined" style={{ fontSize: TILE_ICON[size] }}>
        {icon}
      </span>
    </div>
  );
}

export function StatCard({ icon, label, value, hint, variant = "elevated", className = "" }) {
  const inverse = variant === "primary";
  return (
    <Card variant={variant} className={cx("flex flex-col", className)}>
      {icon && (
        <IconTile
          icon={icon}
          tone={inverse ? "inverse" : "tonal"}
          className={cx("mb-4", !inverse && variant !== "elevated" && "!bg-white/70")}
        />
      )}
      <Eyebrow className={cx("mb-1", inverse && "!text-[var(--on-primary)] opacity-80")}>
        {label}
      </Eyebrow>
      <div className={cx("text-4xl font-extrabold tracking-tight", !inverse && "text-[var(--dark)]")}>
        {value}
      </div>
      {hint && (
        <p className={cx("mt-2 text-sm", inverse ? "opacity-80" : "text-[var(--accent1)]")}>
          {hint}
        </p>
      )}
    </Card>
  );
}

/* ── Controls ───────────────────────────────────────────────────────── */

const BTN_VARIANT = {
  primary: "btn-primary",
  secondary: "btn-secondary",
  ghost: "text-[var(--accent1)] hover:bg-[var(--surface-container-high)] transition-colors",
  danger: "bg-[#fef2f2] text-[#b91c1c] border border-[#fca5a5] hover:bg-[#fee2e2] transition-colors",
  inverse: "bg-[var(--on-primary)] text-[var(--primary)] hover:opacity-90 transition-opacity",
  outline: "border border-white/30 text-[var(--on-primary)] hover:bg-white/10 transition-colors",
};

const BTN_SIZE = {
  sm: "px-4 py-2 text-xs",
  md: "px-5 py-2.5 text-sm",
  lg: "px-6 py-3 text-sm",
  xl: "px-8 py-4 text-base",
};

export function Button({
  variant = "primary",
  size = "md",
  icon,
  iconRight,
  full = false,
  className = "",
  children,
  ...rest
}) {
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-xl font-semibold whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none active:scale-[0.98]",
        BTN_VARIANT[variant],
        BTN_SIZE[size],
        full && "w-full",
        className,
      )}
      {...rest}
    >
      {icon && <span className="material-symbols-outlined" style={{ fontSize: 18 }}>{icon}</span>}
      {children}
      {iconRight && <span className="material-symbols-outlined" style={{ fontSize: 18 }}>{iconRight}</span>}
    </button>
  );
}

export function IconButton({ icon, label, size = 20, className = "", ...rest }) {
  return (
    <button
      aria-label={label}
      title={label}
      className={cx(
        "p-2 rounded-xl text-[var(--accent1)] hover:bg-[var(--surface-container-high)] hover:text-[var(--dark)] transition-colors inline-flex items-center justify-center",
        className,
      )}
      {...rest}
    >
      <span className="material-symbols-outlined" style={{ fontSize: size }}>{icon}</span>
    </button>
  );
}

// Segmented pill toggle (e.g. "All words / Needs practice")
export function Segmented({ options, value, onChange, className = "" }) {
  return (
    <div className={cx("inline-flex gap-1 p-1 rounded-full bg-[var(--surface-container-high)]", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cx(
            "px-4 py-1.5 text-sm font-semibold rounded-full transition-colors",
            value === o.value
              ? "bg-white text-[var(--dark)] shadow-sm"
              : "text-[var(--accent1)] hover:text-[var(--dark)]",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ── Feedback ───────────────────────────────────────────────────────── */

export function ProgressBar({ value, className = "" }) {
  return (
    <div className={cx("h-2 rounded-full overflow-hidden bg-[var(--surface-container-high)]", className)}>
      <div
        className="h-full rounded-full transition-all duration-300 bg-[var(--primary)]"
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}

export function Spinner({ size = 32, className = "" }) {
  return (
    <div
      className={cx("rounded-full border-[3px] animate-spin", className)}
      style={{
        width: size,
        height: size,
        borderColor: "rgba(67,101,101,0.2)",
        borderTopColor: "var(--primary)",
      }}
    />
  );
}

export function LoadingState({ text, className = "" }) {
  return (
    <div className={cx("flex flex-col items-center justify-center gap-4 py-24", className)}>
      <Spinner />
      {text && <p className="text-sm text-[var(--accent1)]">{text}</p>}
    </div>
  );
}

export function EmptyState({ icon, title, description, action, className = "" }) {
  return (
    <div className={cx("flex flex-col items-center text-center py-16 px-6", className)}>
      <IconTile icon={icon} size="lg" className="mb-5 !rounded-full" />
      <p className="font-semibold text-[var(--dark)]">{title}</p>
      {description && <p className="mt-1 text-sm text-[var(--accent1)] max-w-sm">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

// Session results: three stat tiles + review list, shared by Flashcards and Grammar Practice.
export function ResultSummary({ total, correct, totalLabel = "Total" }) {
  return (
    <div className="grid grid-cols-3 gap-4 sm:gap-6 mb-6">
      <StatCard icon="style" label={totalLabel} value={total} />
      <StatCard icon="check_circle" label="Correct" value={correct} variant="accent" />
      <StatCard icon="cancel" label="Wrong" value={total - correct} variant="tonal" />
    </div>
  );
}

export function ResultRow({ correct, children }) {
  return (
    <div
      className="rounded-xl px-4 py-3 flex items-center gap-3"
      style={{ background: correct ? "rgba(239, 254, 229, 0.3)" : "var(--white)" }}
    >
      <span
        className="material-symbols-outlined shrink-0"
        style={{ color: correct ? "#22c55e" : "#ef4444", fontSize: 20, fontVariationSettings: "'FILL' 1" }}
      >
        {correct ? "check_circle" : "cancel"}
      </span>
      {children}
    </div>
  );
}

export function FluencyBadge({ level, className = "" }) {
  if (!level) return null;
  return (
    <span className={cx(`fluency-${level} px-2.5 py-1 rounded-full text-xs font-medium capitalize`, className)}>
      {level}
    </span>
  );
}
