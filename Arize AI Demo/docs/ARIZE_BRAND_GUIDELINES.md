# Arize AI — Brand Guidelines

> Compiled from [arize.com](https://arize.com/) and the official [Arize Brand Hub](https://arize.com/brand/) (scraped 2026-11-18), plus design tokens read from the site's live CSS.
> The Brand Hub is the source of truth. Values marked *(site CSS)* come from the website's stylesheet rather than the Brand Hub and may drift. For unusual cases or approvals, contact **brand@arize.com**. When in doubt, use the Arize master brand.

---

## 1. Brand Overview

| | |
|---|---|
| **Company** | Arize AI |
| **Products** | **Arize AX** (managed AI & agent engineering platform), **Phoenix** (open-source tracing & evaluation for LLM and agent apps), **Alyx** (assistant), **adb** |
| **Homepage headline** | "The agent observability and evaluation platform." |
| **Descriptor** | "Continuously improve AI agents with agent observability, evaluation, tracing, and experimentation." |
| **Sub-message** | "Turn production signals into continual learning so your agents improve with every interaction." |
| **Tagline-style lines** | "Don't ship vibes." · "Infrastructure for self-improving agents." · "Built on open source & open standards." |
| **Primary CTAs** | Start free · Book a demo |

### Brand pillars (strategic rails)
1. **Make it useful** — Turn complexity into tools, signals, and guidance teams can act on.
2. **Find the signal** — Find the precise point of action and help its impact travel.
3. **Strengthen the field** — Strengthen the shared systems, standards, and knowledge AI builders depend on.
4. **Raise the ceiling** — Expand the room for AI builders to think, decide, and build at a higher level.

---

## 2. Logo

- **Symbol:** a pink **chevron**. **Wordmark:** always **lowercase** ("arize").
- **Primary lockup:** pink symbol + black wordmark, on light backgrounds.
- **Reversed lockup:** pink symbol + white wordmark, on dark backgrounds.
- **Monochrome:** all-black on light, all-white on dark.
- **Logomark alone:** use sparingly (e.g. social avatars).

### Do
- Use the full-color logo on light backgrounds; the pink + reversed logo on dark.
- Use all-black (light) or all-white (dark) for monochrome applications.
- Leave a generous, unobstructed clear space around the logo.

### Don't
- Use pink for the wordmark.
- Add strokes or drop shadows.
- Create new color variants — use only supplied files.
- Stretch or distort the logo.
- Retype the wordmark in any other typeface.
- Move or resize the dot in the logomark.

### Sub-brands
**Arize AX** and **Arize Phoenix** are "one family". Use the supplied SVG/PNG lockups from the Brand Hub; don't build your own.

---

## 3. Color

Principle: **Pink for identity, neutrals for structure, accent colors for range.**

### Core colors

| Token | Light mode | Dark mode | Use |
|---|---|---|---|
| **Arize Pink** (Pink 600 / 700) | `#E10C8F` | `#FF44AE` | Primary CTAs, brand details, highlights |
| **Page background** | `#FCFBF7` | `#0C0C0D` | Default page canvas (warm off-white, not pure white) |
| **Text / ink** | `#040301` | `#FCFBF7` | Body and headings |
| **Pink 500 (accessible text pink)** | `#B70070` | — | Pink text on light backgrounds |

### Neutrals — warm greyscale *(site CSS)*

| Token | Hex | Typical use |
|---|---|---|
| Greyscale 100 | `#040301` | Ink |
| Greyscale 200 | `#18160E` | Dark surface |
| Greyscale 300 | `#302E26` | |
| Greyscale 400 | `#4A483F` | Dark-mode borders / rails |
| Greyscale 500 | `#65635A` | Labels, secondary text |
| Greyscale 600 | `#838077` | Placeholders |
| Greyscale 700 | `#A19F94` | |
| Greyscale 800 | `#C0BEB3` | Light-mode borders |
| Greyscale 900 | `#E1DED3` | |
| Greyscale 930 | `#EEE9DF` | |
| Greyscale 960 | `#F3F1EB` | Light surface / cards |
| Greyscale 990 | `#FCFBF7` | Page background |
| Greyscale 1000 | `#FFFFFF` | |

> The neutrals are **warm** (slightly yellow/beige), never cool grey. Keep UI surfaces neutral for clarity.

### Accent colors (foreground / background pairs)

| Accent | FG light | FG dark | BG light | BG dark |
|---|---|---|---|---|
| **Blue** | `#006D9E` | `#09ACE7` | `#ECF7FB` | `#051929` |
| **Violet** | `#5A3FDB` | `#5A3FDB` | `#E9EBFF` | `#1C0C46` |
| **Lime** | `#5F6C00` | `#98AB00` | `#F1F4D5` | `#141900` |
| **Orange** | `#B12D00` | `#FF640D` | `#FFE4D5` | `#2F0505` |
| **Amber** | `#8F5300` | `#DB8A00` | `#FFE7BB` | `#270F00` |

Additional ramp stops seen in the site CSS: Violet 300 `#320E7E`, Violet 400 `#4314B9`, Violet 600 `#7461FE`, Blue 600 `#008CC6`, Pink 900 `#FFC7E4`, Pink 950 `#FFE0F2`, Pink 990 `#FFF4FE`. Phoenix sub-brand blue: `#009DD2` *(site CSS)*.

### Pink rules
- **Never use Arize pink as a full page or section background.** Pink is allowed for primary CTA fills and small highlights.
- The only approved pink background is the **light pink** (e.g. `#FFB5D6`) with readable dark text (`#38001D`). Do not use dark pink or vivid pink as backgrounds.
- **Limit Arize Pink to ~25% of any composition.**
- **No gradients** (e.g. cream-to-pink).
- Don't pair pink with clashing backgrounds (e.g. orange).
- For other pink shades, use a neutral background until the brand team confirms.

### Approved pairings (all WCAG AAA)
| Mode | Background | Text | Accents |
|---|---|---|---|
| Light | `#FCFBF7` | `#020A21` | `#FF13AB`, `#1B000B` |
| Pink shade | `#FFB5D6` | `#38001D` | `#FF13AB`, `#1B000B` |
| Dark | `#100C0B` | `#FFE5EE` | `#FF13AB`, `#EDE9DE` |
| Dark blue shade | `#011C2F` | `#FFE5EE` | `#FF13AB`, `#EDE9DE` |

### Accessibility
- All text must meet **WCAG AA**: 4.5:1 for body, 3:1 for large text.
- Contrast alone does not make a shade brand-approved.
- Accessible pink changes by mode: **Pink 500 for text on light**, **Arize Pink for text on dark**.

### Color in action
- **One clear primary CTA** (pink). Don't give multiple bright buttons equal priority.
- **Let the product lead:** use accents and subtle texture to frame product shots; **preserve product status/data colors** and never recolor the UI.
- Texture and collage must not compete with type or readability.
- Use neutral backgrounds to anchor layered accent colors.

---

## 4. Typography

> "An editorial serif, a precise sans, and a mono for data."

| Role | Typeface | Spec | Use |
|---|---|---|---|
| **Headline** | Display serif — **GT Alpina** (licensed), web alternative **Spectral** | 60px · −30 tracking (−0.03em) · 120% leading · weight 300 · sentence case | Bold, declarative moments; illustrated type |
| **Subhead** | Same serif | 48px · −30 tracking · 120% leading · sentence case | Subheads, pull quotes |
| **Body / UI** | **Geist** | 16px · −10 tracking · 150% leading · weight 400 · sentence case | Body copy and UI |
| **Body small** | Geist | 14px · 150% leading | Secondary text |
| **Mono** | **Geist Mono** | 14px · −10 tracking · 100% leading | Dates, page numbers, technical annotations, code |

- **Spectral** (Google Fonts) is the recommended, freely hostable substitute for the licensed display serif. **Geist** and **Geist Mono** are available from vercel.com/font.
- Use a ~**1.25 type scale** to keep hierarchy tight.
- **Sentence case** everywhere — headlines, subheads, body. (Buttons/labels in forms use uppercase with 0.84px tracking *(site CSS)*.)
- Site responsive sizes *(site CSS)*: display `clamp(34px, 7.8vw, 60px)`, H2 `clamp(30px, 6.25vw, 48px)`, H3 `clamp(26px, 5.2vw, 40px)`, all weight 300 / −0.03em / 120%.

### Fallback stack
```css
--font-serif: "GT Alpina", Spectral, Georgia, serif;
--font-sans:  Geist, system-ui, sans-serif;
--font-mono:  "Geist Mono", ui-monospace, monospace;
```

---

## 5. Voice & Tone

Five brand attributes:

| Attribute | Means | In practice |
|---|---|---|
| **Rigorous** | Methodical, exacting, developer-fluent | Disciplined, deep, careful with complex problems |
| **Open** | Curious, transparent, expansive | Learning, sharing, making space for possibility |
| **Embedded** | In the mix, eye-to-eye, useful | Stay close to the people and systems we build for |
| **Dynamic** | Active, iterative, propulsive | Testing, learning, improving, building in real time |
| **Grounded** | Steady, principled, low-hype | Clear on what we believe and what matters most |

### Writing guidance (inferred from site copy)
- Short, declarative sentences. Plain, technical, practitioner-to-practitioner.
- Lead with outcomes: *find issues, get proposed fixes, improve with every interaction.*
- **Low-hype:** no superlative marketing fluff; the one playful line is "Don't ship vibes."
- Sentence case. Concrete nouns (traces, evals, agents, signals).
- CTA language: **Start free**, **Book a demo**, **Sign in**, **Start in the product / Start in your terminal**.

---

## 6. Imagery & Texture

> "Imagery is the data, made visible."

- Imagery draws on **natural forms that leave visible traces** — topography, ripples, currents, growth patterns — as a physical analogue for observability.
- **Collage** combines natural textures with technical signal patterns. Meaning should come from how layers relate; it must communicate an idea, not just decorate.
- Four collage formations: **Layers** (most common), **X-ray**, **Rising**, **Scale** (Rising/Scale represent impact).

### Do
- Use **tonal shades of the same color**.
- Pair pastel shades with darker detail layers (or bright with darker detail layers).

### Don't
- Use bright accent colors in detail layers.
- Mix competing pastel (or competing bright) shades.
- Let texture overlap key messages or reduce legibility.

### Asset rule (important for AI/automation)
The Brand Hub states that textures and collage motifs are **fixed brand assets**. Use them only as supplied. **Do not generate, extend, redraw, continue, or combine** them into new motifs. If a needed texture isn't available, contact **brand@arize.com**.

---

## 7. UI Components *(site CSS)*

| Element | Spec |
|---|---|
| Page background | `#FCFBF7` (light) / `#0C0C0D` (dark) |
| Cards / surfaces | `#F3F1EB` light · `#18160E` dark |
| Borders | `#C0BEB3` light · `#4A483F` dark |
| Secondary label text | `#65635A` |
| Inputs | bg `#FCFBF7` / dark `#18160E`; border `#C0BEB3` / dark `#4A483F`; height 32px; 14px text |
| Form buttons (HubSpot) | bg `#5A3FDB` (dark `#320E7E`), text `#FCFBF7`, 14px, uppercase, 0.84px tracking |
| Focus outline | `#5A3FDB` |
| Corner radius | Small (≈6px) |
| Primary CTA | Arize Pink fill, one per view |
| Theme support | Full light **and** dark mode |

> Note: the site's embedded form buttons use violet while the Brand Hub specifies **pink for primary CTAs**. Follow the Brand Hub for new work.

---

## 8. Quick Reference

```css
:root {
  /* Brand */
  --arize-pink:        #E10C8F;   /* dark mode: #FF44AE */
  --arize-pink-text:   #B70070;   /* text on light */

  /* Neutrals */
  --bg:                #FCFBF7;   /* dark: #0C0C0D */
  --ink:               #040301;   /* dark: #FCFBF7 */
  --surface:           #F3F1EB;   /* dark: #18160E */
  --border:            #C0BEB3;   /* dark: #4A483F */
  --label:             #65635A;

  /* Accents (fg) */
  --blue:    #006D9E;  --violet: #5A3FDB;  --lime:  #5F6C00;
  --orange:  #B12D00;  --amber:  #8F5300;
}
```

### Checklist before shipping
- [ ] Warm off-white / near-black backgrounds — **no pink backgrounds, no gradients**
- [ ] Pink ≤ ~25% of composition; one primary pink CTA
- [ ] Lowercase "arize" wordmark, supplied logo files only, clear space respected
- [ ] Serif headlines (sentence case), Geist body, Geist Mono for data
- [ ] WCAG AA contrast on all text
- [ ] Product UI colors untouched
- [ ] Only supplied textures/collage assets
- [ ] Copy is rigorous, grounded, low-hype

---

*Source: https://arize.com/brand/ · https://arize.com/ · Contact: brand@arize.com*
