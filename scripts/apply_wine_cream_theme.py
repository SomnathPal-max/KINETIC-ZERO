import re

with open("app/static/console/console.css", "r", encoding="utf-8") as f:
    css = f.read()

# Replace root palette with Red Wine & Milky Cream Palette
new_root = """/* KINETIC-ZERO v3.5 Enterprise Design System
   Red Wine & Milky Cream Palette — Deep Bordeaux, Velvet Merlot & Frosted Milky Warmth */

:root {
  /* Red Wine & Milky Cream Palette */
  --bg-canvas: #13080e;        /* Deep Noir Wine */
  --bg-surface: #1e0c16;       /* Rich Cabernet Surface */
  --bg-elevated: #2a1120;      /* Elevated Merlot Card */
  --bg-hover: #3d182e;         /* Spiced Wine Hover */
  --bg-glass: rgba(30, 12, 22, 0.85);

  --border-subtle: rgba(255, 246, 240, 0.08); /* Milky Hairline */
  --border-strong: rgba(255, 246, 240, 0.16); /* Milky Outline */
  --border-focus: #fb7185;

  --brand-primary: #e11d48;    /* Radiant Red Wine / Ruby */
  --brand-hover: #be123c;      /* Deep Vintage Merlot */
  --brand-gradient: linear-gradient(135deg, #e11d48 0%, #9f1239 60%, #4c0519 100%);
  --brand-glow: rgba(225, 29, 72, 0.25);

  --text-primary: #fff6f0;     /* Pure Milky Cream */
  --text-secondary: #e5d3c8;   /* Warm Frosted Latte */
  --text-muted: #a89287;       /* Soft Mocha Cream */

  --status-emerald: #10b981;
  --status-emerald-bg: rgba(16, 185, 129, 0.12);
  --status-emerald-border: rgba(16, 185, 129, 0.35);

  --status-rose: #f43f5e;
  --status-rose-bg: rgba(244, 63, 94, 0.12);
  --status-rose-border: rgba(244, 63, 94, 0.35);

  --status-amber: #f59e0b;
  --status-amber-bg: rgba(245, 158, 11, 0.12);
  --status-amber-border: rgba(245, 158, 11, 0.35);

  --status-blue: #38bdf8;
  --status-blue-bg: rgba(56, 189, 248, 0.12);
  --status-blue-border: rgba(56, 189, 248, 0.35);

  --font-sans: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;

  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;

  --shadow-sm: 0 1px 3px rgba(19, 8, 14, 0.5);
  --shadow-md: 0 4px 16px rgba(19, 8, 14, 0.6);
  --shadow-lg: 0 12px 36px rgba(19, 8, 14, 0.75);
}"""

# Replace root
css = re.sub(r'/\* KINETIC-ZERO.*?\}\n', new_root + '\n', css, flags=re.DOTALL)

# Replace remaining indigo/blue hardcoded styles with milky red wine
replacements = [
    ("rgba(99, 102, 241, 0.4)", "rgba(225, 29, 72, 0.45)"),
    ("rgba(99, 102, 241, 0.12)", "rgba(225, 29, 72, 0.15)"),
    ("rgba(99, 102, 241, 0.25)", "rgba(225, 29, 72, 0.35)"),
    ("rgba(99, 102, 241, 0.35)", "rgba(225, 29, 72, 0.4)"),
    ("rgba(99, 102, 241, 0.15)", "rgba(225, 29, 72, 0.18)"),
    ("rgba(99, 102, 241, 0.08)", "rgba(225, 29, 72, 0.12)"),
    ("rgba(99, 102, 241, 0.05)", "rgba(225, 29, 72, 0.08)"),
    ("rgba(99, 102, 241, 0.22)", "rgba(225, 29, 72, 0.3)"),
    ("rgba(99, 102, 241, 0.2)", "rgba(225, 29, 72, 0.28)"),
    ("rgba(99, 102, 241, 0.3)", "rgba(225, 29, 72, 0.35)"),
    ("rgba(99, 102, 241, 0.6)", "rgba(225, 29, 72, 0.75)"),
    ("rgba(99,102,241,0.06)", "rgba(225,29,72,0.1)"),
    ("rgba(99,102,241,0.15)", "rgba(225,29,72,0.2)"),
    ("#a5b4fc", "#ffe4e6"),
    ("#818cf8", "#fb7185"),
    ("#6366f1", "#e11d48"),
]

for old, new in replacements:
    css = css.replace(old, new)

# Update guide banner gradient to red wine tones
css = css.replace(
    "rgba(22, 31, 48, 0.8) 0%, rgba(16, 22, 35, 0.8) 100%",
    "rgba(42, 17, 32, 0.85) 0%, rgba(30, 12, 22, 0.85) 100%"
)

# Update inbound channels gradient to red wine tones
css = css.replace(
    "rgba(22, 31, 48, 0.7) 0%, rgba(16, 22, 35, 0.7) 100%",
    "rgba(42, 17, 32, 0.8) 0%, rgba(30, 12, 22, 0.8) 100%"
)

# Update brand logo styling to red wine velvet with milky cream text
css = css.replace(
    ".brand-logo {\n  width: 32px;\n  height: 32px;\n  border-radius: var(--radius-md);\n  background: var(--brand-gradient);",
    ".brand-logo {\n  width: 32px;\n  height: 32px;\n  border-radius: var(--radius-md);\n  background: linear-gradient(135deg, #e11d48 0%, #881337 100%);\n  box-shadow: 0 2px 10px rgba(225, 29, 72, 0.35);"
)

with open("app/static/console/console.css", "w", encoding="utf-8") as f:
    f.write(css)

print("SUCCESS: Updated console.css with Red Wine and Milky Cream palette!")
