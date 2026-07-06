---
name: Steam Group Recommender Neon Command
description: A dark neon multiplayer recommendation cockpit for Steam groups.
colors:
  void: "#060912"
  deck: "#0b1020"
  panel: "#11182a"
  panel-strong: "#17213a"
  line: "#263656"
  text: "#edf7ff"
  muted: "#9fb0c8"
  cyan: "#33f5ff"
  violet: "#9d6bff"
  lime: "#a8ff60"
  amber: "#ffd166"
  danger: "#ff5d8f"
typography:
  headline:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 800
    lineHeight: "34px"
    letterSpacing: "0"
  title:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 700
    lineHeight: "24px"
  body:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "22px"
  label:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 700
    lineHeight: "16px"
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
spacing:
  xs: "6px"
  sm: "10px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.cyan}"
    textColor: "{colors.void}"
    rounded: "{rounded.md}"
    padding: "11px 16px"
  card-game:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "0"
---

# Design System: Steam Group Recommender Neon Command

## 1. Overview

**Creative North Star: "Neon Co-op Command Deck"**

This product is a dark, focused recommendation cockpit for a group of players deciding what to play together. It should feel game-native and technically sharp, but still behave like a reliable tool: clear inputs, readable evidence, fast comparison, and predictable states.

The visual system uses a near-black void background, layered blue-black panels, electric cyan for primary actions, violet for discovery accents, and lime for positive recommendation strength. The look should suggest Steam, multiplayer sessions, and tactical selection without turning into decorative cyberpunk noise.

**Key Characteristics:**
- Dark command surface with restrained neon emphasis.
- Dense but scannable controls and recommendation cards.
- Recommendation evidence is more important than decoration.
- Motion is subtle and state-based.

## 2. Colors

The palette is a cool dark deck with three neon signals: cyan for action, lime for match strength, violet for discovery.

### Primary
- **Electric Cyan** (#33f5ff): Primary buttons, focus rings, active input glow, and key interactive affordances.

### Secondary
- **Arcade Violet** (#9d6bff): Secondary discovery accents, section dividers, and fresh-track cues.
- **Signal Lime** (#a8ff60): Recommendation strength and positive match indicators.

### Neutral
- **Void Black** (#060912): Page background.
- **Deck Navy** (#0b1020): Main app surface.
- **Panel Blue-Black** (#11182a): Cards and form panels.
- **Muted Steel** (#9fb0c8): Secondary text and helper copy.

### Named Rules
**The Glow Budget Rule.** Neon glow is reserved for focus, hover, selected states, and recommendation strength. Do not glow every container.

## 3. Typography

**Display Font:** Inter with system fallbacks  
**Body Font:** Inter with system fallbacks  
**Label/Mono Font:** Inter with tabular numerals where needed

**Character:** Crisp, compact, and readable. This is a product UI, so the typography should feel like an instrument panel rather than a poster.

### Hierarchy
- **Headline** (800, 28px, 34px): Page title and major workflow framing.
- **Title** (700, 18px, 24px): Section and card titles.
- **Body** (400, 14px, 22px): Reasons, helper text, status, and supporting copy.
- **Label** (700, 12px, 16px): Field labels, badges, and compact metadata.

### Named Rules
**The No Poster Type Rule.** Keep product headings compact. Do not use oversized hero typography inside the tool.

## 4. Elevation

Depth is conveyed through tonal layering, crisp borders, and small neon state glows. Static cards are mostly flat; hover and focus states may lift slightly with a tight shadow.

### Shadow Vocabulary
- **Panel Hover** (`0 10px 28px rgba(51, 245, 255, 0.10)`): Use only on interactive result cards.
- **Focus Glow** (`0 0 0 3px rgba(51, 245, 255, 0.18)`): Use for keyboard focus and active inputs.

### Named Rules
**The Flat-Until-Interactive Rule.** Surfaces stay calm until the user focuses, hovers, or selects them.

## 5. Components

### Buttons
- **Shape:** Tight rounded rectangle (8px).
- **Primary:** Electric cyan fill, void text, compact padding.
- **Hover / Focus:** Slight lift, cyan glow, visible outline.
- **Secondary:** Transparent panel fill with cyan border and readable text.

### Chips
- **Style:** Dark blue pill with subtle cyan/violet border.
- **State:** Match and source chips can use lime or violet text, but background stays dark.

### Cards / Containers
- **Corner Style:** 12px for game cards, 8px for form panels.
- **Background:** Layered blue-black panel surfaces.
- **Shadow Strategy:** No broad soft shadows at rest; tight neon hover only.
- **Border:** 1px blue-gray border with optional neon top accent for recommendation cards.
- **Internal Padding:** 16px to 18px.

### Inputs / Fields
- **Style:** Dark field, 1px line, 8px radius.
- **Focus:** Cyan border and focus glow.
- **Error / Disabled:** Use red/pink text and border, never color alone.

### Navigation
- **Style:** Single-page stacked tool layout. Controls sit first, then taste summary, then recommendation sections.

### Game Recommendation Card
The card must foreground cover art, recommendation percent, title, source chips, and AI reason. The reason is the trust payload; it needs a readable prose zone, not a tiny caption.

## 6. Do's and Don'ts

### Do:
- **Do** use cyan for action and focus, lime for recommendation strength, and violet for discovery or fresh-track cues.
- **Do** keep cards dense enough for comparison while giving AI reasons enough line height.
- **Do** make focus states visible on every input and button.
- **Do** keep body text high contrast against dark panels.

### Don't:
- **Don't** use plain white dashboard surfaces.
- **Don't** use purple gradient mush or decorative glassmorphism.
- **Don't** add broad card shadows plus borders as decoration.
- **Don't** turn every element neon; glow must mean state or importance.
- **Don't** hide the recommendation reason behind hover-only interactions.
