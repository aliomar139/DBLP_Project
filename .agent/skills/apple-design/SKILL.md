---
name: apple-design
description: "Apple Human Interface Guidelines (HIG) and fluid design skill. Use when building or styling web, mobile, or desktop interfaces with Apple's aesthetic standards: SF Pro typography, 8pt spatial grid, translucency/vibrancy materials, fluid spring physics, deference to content, and minimalist elegance."
license: MIT
metadata:
  tags: "Apple, HIG, Design System, UI, UX, Styling, Motion"
  category: "design"
---

# Apple Design Skill

You are an expert product designer and UI engineer steeped in Apple's design philosophy and Human Interface Guidelines (HIG). Your objective is to craft interfaces that feel calm, native, deference-driven, and refined.

---

## 1. Core Principles

1. **Clarity**:
   - Text is legible at every size.
   - Icons are precise and lucid.
   - Adornments are subtle and purposeful.
   - Functionality motivates every visual element.

2. **Deference**:
   - The UI recedes; the content takes center stage.
   - Fluid motion and crisp, lightweight controls help users understand and interact with the content without competing with it.
   - Minimize unnecessary chrome, borders, and decorative noise.

3. **Depth**:
   - Distinct visual layers and realistic motion convey hierarchy and spatial relationships.
   - Touch and pointer interactions produce immediate, delightful tactile responses.
   - Use background blur (`backdrop-filter: blur(...)`), translucency, and elevation rather than harsh, solid separators.

---

## 2. Visual & Architectural Rules

### Typography
- **Primary Typeface**: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", sans-serif`.
- **Optical Sizing**: Use SF Pro Display (or heavier tracking) for headlines >= 20px; SF Pro Text for body copy <= 19px.
- **Hierarchy**: Strict scale (e.g. Large Title 34pt, Title 1 28pt, Title 2 22pt, Title 3 20pt, Headline 17pt/600, Body 17pt/400, Subhead 15pt, Footnote 13pt, Caption 11pt).
- **Leading & Tracking**: Maintain comfortable line height (1.4–1.6 for body) with tight, refined letter-spacing for large titles (`-0.02em` to `-0.04em`).

### Spatial System & Layout
- **8pt Grid**: All margins, paddings, and component sizes align to 8px increments (4px for micro-spacing, 8px, 12px, 16px, 24px, 32px, 48px).
- **Corner Radii**: Apple-style continuous curves (squircle) using `border-radius: 10px` to `16px` for cards/panels, `6px` to `8px` for controls, or pill shapes for tags.
- **Breathing Room**: Generous negative space around primary interactive elements and sections.

### Color & Materials
- **Translucency & Vibrancy**: Subtle backdrop blur with semi-transparent panels:
  - Light mode: `rgba(255, 255, 255, 0.75)` with `backdrop-filter: blur(20px)`.
  - Dark mode: `rgba(30, 30, 30, 0.75)` with `backdrop-filter: blur(20px)`.
- **Subtle Hairlines**: Hairline borders using `rgba(0, 0, 0, 0.08)` in light mode or `rgba(255, 255, 255, 0.12)` in dark mode.
- **System Accents**: Use refined system tint colors (e.g. Apple Blue `#007AFF`, Indigo `#5856D6`, Teal `#30B0C7`, Amber `#FF9500`).

### Motion & Micro-interactions
- **Spring Physics**: Natural spring motion (`cubic-bezier(0.25, 1, 0.5, 1)` or `spring(1, 80, 10, 0)`). Avoid linear or robotic ease-in-out curves.
- **Interruptible Transitions**: Transitions should never block user interaction and must complete under 250–350ms.
- **Active State Feedback**: Scale transforms on click/tap (`transform: scale(0.98)` or `scale(0.96)`) with instant response.

