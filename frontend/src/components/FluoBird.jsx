// Animated brand bird: flies in from the left, lands on the branch, then idles
// (gentle bob + occasional blink). Honors prefers-reduced-motion via CSS.
// Colors mirror public/favicon.svg.
export default function FluoBird({ className = "" }) {
  return (
    <svg
      viewBox="0 0 320 180"
      className={`fluo-bird ${className}`}
      aria-hidden="true"
      focusable="false"
    >
      {/* branch */}
      <g className="fluo-branch">
        <path
          d="M-10 138 C 60 118 120 150 210 132 C 260 122 300 135 330 128"
          stroke="#2d3433"
          strokeWidth="6"
          fill="none"
          strokeLinecap="round"
        />
        <path
          d="M118 142 C 108 156 96 160 82 166"
          stroke="#2d3433"
          strokeWidth="4"
          fill="none"
          strokeLinecap="round"
        />
        <path d="M82 166 c -7 -1 -15 6 -16 15 c 9 0 15 -7 16 -15 Z" fill="#7aa08f" />
        <path d="M232 128 C 244 116 258 110 274 114" stroke="#2d3433" strokeWidth="4" fill="none" strokeLinecap="round" />
        <path d="M274 114 c 6 -3 14 -9 16 -18 c -9 2 -15 9 -16 18 Z" fill="#7aa08f" />
      </g>

      {/* bird: flight path + idle bob applied on the group */}
      <g className="fluo-bird-flight">
        <g className="fluo-bird-idle">
          {/* body (bounding box centered around 0,0 so transforms feel natural) */}
          <g transform="translate(-36 -34)">
            <path
              d="M21 43
                 C 23 40 25 38.5 27 38
                 C 29 30 35 24 42 23
                 C 48 22.5 52 25.5 52 28
                 L 56.5 29.5 L 52 31
                 C 51.5 39 46 45.5 36 46
                 C 30 46.5 25 45.5 21 43 Z"
              fill="#f1cc83"
            />
            {/* far wing */}
            <path
              className="fluo-wing fluo-wing-back"
              d="M30 40 C 32 33 40 30 47 32 C 44 36 38 40 30 40 Z"
              fill="#c9a15b"
            />
            {/* near wing */}
            <path
              className="fluo-wing fluo-wing-front"
              d="M28 42 C 30 35 38 32 45 34 C 42 38 36 42 28 42 Z"
              fill="#d9b06a"
            />
            {/* eye */}
            <circle className="fluo-eye" cx="47" cy="27.5" r="1.3" fill="#2d3433" />
            {/* feet, fade in on landing */}
            <g className="fluo-feet" stroke="#2d3433" strokeWidth="1.4" strokeLinecap="round" fill="none">
              <path d="M31 46 l -1.5 4.5 M31 46 l 1 4.5 M31 46 l 3 3.5" />
              <path d="M37 46.5 l -1.5 4.5 M37 46.5 l 1 4.5 M37 46.5 l 3 3.5" />
            </g>
          </g>
        </g>
      </g>
    </svg>
  );
}
