import {
  CEFR_LEVELS,
  CEFR_DESCRIPTIONS,
  SUB_LEVELS,
  splitLevel,
  joinLevel,
  levelDescription,
} from "../utils.jsx";

/**
 * Two-row picker for a learner level: a CEFR band (A1–C2) and a sub-level
 * (beginner / intermediate / advanced) within it.
 *
 * Props:
 *  - value: "B1-intermediate"
 *  - onChange: (level) => void
 *  - inverse: render on a dark/primary background
 *  - compact: tighter spacing
 */
export default function LevelPicker({ value, onChange, inverse = false, compact = false }) {
  const { cefr, sub } = splitLevel(value);

  const base = compact ? "px-2.5 py-1 text-xs" : "px-3.5 py-1.5 text-sm";
  const on = inverse
    ? "bg-white text-[var(--primary)] shadow-sm"
    : "bg-[var(--primary)] text-[var(--on-primary)] shadow-sm";
  const off = inverse
    ? "text-white/80 hover:bg-white/15"
    : "text-[var(--accent1)] hover:bg-[var(--surface-container-high)] hover:text-[var(--dark)]";
  const track = inverse ? "bg-white/12" : "bg-[var(--surface-container-low)]";
  const label = inverse ? "text-white/70" : "text-[var(--accent1)]";

  const pill = (active, extra = "") =>
    `${base} rounded-full font-bold transition-colors ${active ? on : off} ${extra}`;

  return (
    <div className={compact ? "space-y-2" : "space-y-3"}>
      <div>
        <div className={`text-[10px] font-bold uppercase tracking-widest mb-1.5 ${label}`}>
          CEFR band
        </div>
        <div className={`inline-flex flex-wrap gap-1 p-1 rounded-full ${track}`}>
          {CEFR_LEVELS.map((c) => (
            <button
              key={c}
              type="button"
              title={CEFR_DESCRIPTIONS[c]}
              onClick={() => onChange(joinLevel(c, sub))}
              className={pill(c === cefr)}
            >
              {c}
            </button>
          ))}
        </div>
      </div>
      <div>
        <div className={`text-[10px] font-bold uppercase tracking-widest mb-1.5 ${label}`}>
          Within {cefr}
        </div>
        <div className={`inline-flex flex-wrap gap-1 p-1 rounded-full ${track}`}>
          {SUB_LEVELS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => onChange(joinLevel(cefr, s))}
              className={pill(s === sub, "capitalize")}
            >
              {s}
            </button>
          ))}
        </div>
      </div>
      <p className={`text-xs ${label}`}>{levelDescription(joinLevel(cefr, sub))}</p>
    </div>
  );
}
