---
name: Neutral Ground
description: An international football yearbook; each tournament is a volume, every match priced before kickoff and scored against the result.
colors:
  spot: "#1e3fae"
  spot-ink: "#ffffff"
  tint-away: "#8a9edc"
  tint-draw: "#cad3ef"
  paper: "#f5f6f2"
  paper-2: "#eceee8"
  ink: "#14171c"
  ink-2: "#3a404a"
  muted: "#5d646f"
  rule: "#d4d8dd"
  rule-strong: "#14171c"
  focus: "#1e3fae"
  dark-paper: "#0f1217"
  dark-paper-2: "#161a21"
  dark-ink: "#e8ebf0"
  dark-ink-2: "#c3c8d1"
  dark-muted: "#98a0ad"
  dark-rule: "#2a303a"
  dark-spot: "#8aa2ff"
  dark-tint-away: "#4a5ea6"
  dark-tint-draw: "#2c3656"
typography:
  display:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(6rem, 22vw, 13.5rem)"
    fontWeight: 850
    lineHeight: 0.85
    letterSpacing: "-0.02em"
    fontVariation: "'wdth' 62"
  headline:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(2.5rem, 7vw, 4.5rem)"
    fontWeight: 800
    lineHeight: 1
    fontVariation: "'wdth' 75"
  title:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "2rem"
    fontWeight: 800
    lineHeight: 1.05
    fontVariation: "'wdth' 75"
  lede:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.3125rem"
    fontWeight: 400
    lineHeight: 1.375
  body:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "'tnum'"
  table:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "'tnum'"
  prose:
    fontFamily: "'Source Serif 4', ui-serif, Georgia, serif"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    letterSpacing: "0.1em"
rounded:
  none: "0px"
spacing:
  gutter-sm: "16px"
  gutter-md: "32px"
  gutter-lg: "48px"
  row: "12px"
  section: "96px"
  column-gap: "64px"
  container: "82rem"
components:
  nav-link:
    textColor: "{colors.ink-2}"
    typography: "{typography.table}"
    rounded: "{rounded.none}"
    padding: "12px 12px"
  nav-link-active:
    textColor: "{colors.spot}"
  segment-option:
    textColor: "{colors.ink-2}"
    typography: "{typography.table}"
    padding: "10px 12px"
  segment-option-active:
    textColor: "{colors.spot}"
  match-row:
    backgroundColor: "{colors.paper}"
    typography: "{typography.body}"
    padding: "12px 8px"
  match-row-hover:
    backgroundColor: "{colors.paper-2}"
  prob-bar-row:
    height: "10px"
    rounded: "{rounded.none}"
  prob-bar-large:
    height: "36px"
    rounded: "{rounded.none}"
  bracket-card:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.none}"
    padding: "8px 12px"
  mark-called:
    backgroundColor: "{colors.ink}"
    rounded: "{rounded.none}"
    size: "48px"
  mark-missed:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.none}"
    size: "48px"
  running-head:
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    padding: "10px 0"
---

# Design System: Neutral Ground

## Overview

**Creative North Star: "The Football Yearbook"**

Neutral Ground is printed, not rendered. Each tournament is a volume of a yearbook, set in a restrained two-color press run: near-black ink on off-white paper, with one ultramarine spot color and its tints. The unit of the record is the match row, built around a home / draw / away probability bar with the actual result framed in ink over it. Everything on a page either is a match, counts matches, or links back to one.

Density is that of a reference book: hairline rules between rows, heavy 2px rules opening each table or list, tabular figures everywhere, condensed grotesk numerals for the numbers that matter. Pages carry running heads naming the volume, the way a printed yearbook names its section at the top of every spread. There are no cards with shadows, no textures, no stains, no props; the paper is flat and the ink sits on it.

Misses are content. A wrong call is struck through, and the stroke's weight scales with how sure the model was, so the most confident misses are the heaviest marks on the page. Dark mode is the same press run on ink-dark stock, not a separate theme. The world refuses the dark stat-card dashboard and the betting coupon.

**Key Characteristics:**
- Two-color print: ink plus one ultramarine spot; draw and away are tints of the spot.
- Square corners everywhere; hairline and heavy rules instead of boxes and shadows.
- Condensed Archivo display numerals over a plain Archivo body; Source Serif 4 only for long-form prose.
- Running heads in small tracked capitals name the volume and the stage on every page.
- Strike weight encodes confidence on every miss.

## Colors

One spot ink and its tints on paper and ink; nothing else carries hue.

### Primary
- **Ultramarine Spot** (`spot`): the press's single color. The home segment of every probability bar, the "/104" in the masthead numeral, the "Ground" in the wordmark, active navigation, links in prose, the tick on a called verdict, the "Happened" bar in the reliability table, and the focus ring. Text on it uses **Spot Ink** (`spot-ink`, white in light, paper-dark in dark).

### Secondary
- **Mid Ultramarine Tint** (`tint-away`): the away segment of the probability bar and the "Said" (stated confidence) bar in the reliability table.
- **Light Ultramarine Tint** (`tint-draw`): the draw segment of the probability bar and the empty track behind stage-ledger bars.

### Neutral
- **Off-White Paper** (`paper`): page background, row background, bracket card background, the empty interior of a missed mark.
- **Turned Page** (`paper-2`): the only hover fill; rows, cards, and links shift to it on hover.
- **Press Ink** (`ink`): body text, solid called marks, the result frame on the probability bar, the strike on a miss.
- **Second Ink** (`ink-2`): secondary copy, ledes, inactive nav.
- **Muted Ink** (`muted`): running heads, column heads, percentages beside a pick, search placeholders.
- **Hairline** (`rule`): 1px row separators and the bracket card border.
- **Heavy Rule** (`rule-strong`, equal to ink): 2px rules under the masthead, above the footer, and opening every table and list.

### Dark stock
The `dark-*` tokens are the same roles reprinted on ink-dark paper (`dark-paper`). The spot lightens to `dark-spot` so it holds on dark stock; tints darken (`dark-tint-away`, `dark-tint-draw`) so the order home (brightest) / draw / away keeps its contrast relationship to the paper. `rule-strong` becomes the dark ink, so heavy rules stay ink-colored. Theme resolves from `prefers-color-scheme` unless a `data-theme` attribute (set by the header toggle and stored as `ng-theme`) overrides it.

### Named Rules
**The One Spot Rule.** Ultramarine and its two tints are the only hues. Never add a red for misses or a green for hits; a miss is shown by the strike, not by color.

**The Fixed Segment Rule.** Home is always solid spot, draw always the light tint, away always the mid tint, in that left-to-right order. Meaning rides on position and labels as well as color.

## Typography

**Display Font:** Archivo (variable width 62–125, weight 400–900), with ui-sans-serif, system-ui fallback
**Body Font:** Archivo
**Prose Font:** Source Serif 4 (optical size 8–60), with ui-serif, Georgia fallback

**Character:** One grotesk family stretched to do two jobs: squeezed and heavy for numerals and headings, normal width for reading. The serif appears only where the site explains itself at length.

### Hierarchy
- **Display** (850, 62% width, `clamp(6rem, 22vw, 13.5rem)` on Home, `clamp(3.5rem, 11vw, 8rem)` for a match score, `clamp(3.5rem, 12vw, 9rem)` for a nation name, line-height 0.85, -0.02em): the one headline number or name per page.
- **Headline** (800, 75% width, `clamp(2.5rem, 7vw, 4.5rem)`, line-height 1): page titles on index pages (Matches, Nations, Method).
- **Title** (800, 75% width, 2rem, line-height 1.05): section titles in the Home side column; group codes and team names in bracket and groups use the same condensed 800 at 1.25rem.
- **Lede** (400, 1.3125rem, snug): the one sentence that states what a big number means.
- **Body** (400, 16px, 1.5, tabular figures): default text. Match fixtures in rows run at 1.0625rem semibold; tables at 0.9375rem.
- **Prose** (Source Serif 4, 400, 1.125rem, 1.65, max 68ch): Method page and the "How it works" link only.
- **Label / Running head** (400, 0.75rem, 0.1em tracking, uppercase, muted): running heads, column heads, stage labels under the mark grid, small section labels.

### Named Rules
**The Tabular Figures Rule.** The body sets `tabular-nums` globally. Every number in a column lines up; never turn it off.

**The Condensed Numeral Rule.** Scores, counts, and record numbers that carry the page are set condensed and extra-bold; supporting numbers stay in body weight with tabular figures.

## Layout

A single centered column, max 82rem, with side gutters of 16px (mobile), 32px (from 640px), and 48px (from 1024px). Masthead and footer span full width with 2px ink rules; the running head sits in its own band under the masthead, separated by a hairline, with its two halves pushed to opposite edges.

Home opens with a 7fr / 5fr split at 1024px: the record numeral and its mode line on the left, the stage ledger table on the right. Below a 2px rule sits the mark grid. Later sections use an 18rem title column beside the content (64px gap) and are spaced 96px apart. Match pages center the content at max 56rem. Groups lay out in two columns from 1280px; the knockout bracket is a five-column grid with a 64rem minimum width that scrolls horizontally below 1024px.

The match row is a four-column grid on desktop (4.5rem date, flexible fixture, 10–14rem bar, 11rem verdict) and restacks on mobile into date, fixture plus verdict, then a full-width bar. Rows are 12px tall in padding with a hairline beneath.

### Named Rules
**The Running Head Rule.** Every page except error pages opens with a running head: the volume (and stage, for a match) on the left, the date range or date and venue on the right.

## Elevation & Depth

Flat. There are no shadows anywhere. Depth is conveyed by rule weight (1px hairline vs 2px ink) and by the single hover fill (`paper-2`). The probability bar's result frame is drawn as an ink border overlapping the segment by 2–4px, which is the only thing that sits "above" anything else.

### Named Rules
**The Flat Press Rule.** Ink sits on paper. No box-shadows, no blur, no gradients, no textures.

## Shapes

Square corners throughout (0px). Containers are drawn with rules, not filled panels: lists and tables open with a 2px ink rule and separate rows with 1px hairlines. The only bordered boxes are bracket match cards (1px hairline, ink on hover) and the mark grid squares (1.5px ink). Segments of the probability bar are separated by a 1px gap of paper.

## Components

### Probability bar (signature)
The unit of the record. A full-width bar split home / draw / away in proportion to the model's pre-tournament probabilities (draw omitted where zero, as in knockouts), segments separated by 1px gaps.
- **Sizes:** row (10px tall) and large (36px tall, with labels beneath each segment: code or "Draw" plus the percentage to one decimal, the result's label bold ink, the rest muted).
- **Result frame:** an ink border around the actual outcome's segment, 2px inset -3px in a row, 3px inset -4px when large.
- **Miss strike:** when the pick was wrong, a horizontal ink bar runs through the middle of the picked segment, its height from the strike-weight scale (max 6px in a row, 10px large).
- **Accessibility:** exposed as an image with a text description of all three probabilities and the result.

### Match row
Date (running head, with the stage underneath when rows mix stages), "Home score–away" with the score condensed extra-bold, the probability bar, and the verdict. The whole row is one link; hover fills it with `paper-2` and underlines team names. Lists open with a 2px ink rule.

### Verdict
- **Called:** ultramarine tick (16px, stroke 3), pick name semibold, the pick's percentage muted.
- **Missed:** pick name and percentage struck through, thickness from the strike-weight scale (max 1.5px in compact rows, 4px in the match-page sentence). The full form adds "result had N%" in muted.

### Mark grid
Every match of the volume as one square mark, in date order, grouped by stage in six-row columns, each stage labeled beneath with its called count. Marks are 18px (mobile), 24px (640px), 36px (1024px), 48px (1280px), with a 1.5px ink border.
- **Called:** solid ink; hover turns it spot.
- **Missed:** paper with a single diagonal stroke from bottom-left to top-right, weight from the strike-weight scale (1–6px); hover fills `paper-2`.
- Hover or focus prints the match's full sentence in a live region beneath the grid. Marks ink in on first view (220ms clip reveal, 7ms stagger per mark), disabled under reduced motion.

### Navigation
Wordmark "NEUTRAL GROUND" condensed extra-bold uppercase, "Ground" in spot. Nav links are semibold 0.9375rem with a 2px bottom border: transparent at rest, spot with spot text when active, ink text on hover. On mobile the links drop to a full-width scrolling row under the wordmark. A 40px theme toggle at the right cycles system / light / dark.

### Segmented filter
Radio-group of text options on a hairline baseline: semibold 0.9375rem, active option takes a 2px spot underline and spot text. Same treatment as nav, used for stage and outcome filters on Matches.

### Search field
No box: a 2px ink underline with a muted search icon; the underline turns spot on focus.

### Bracket card
1px hairline box on paper, 8px by 12px padding, two team lines (winner bold), a row-size probability bar, then the compact verdict and "pens" when a shootout decided it. Border turns ink on hover.

### Stage ledger and data tables
Running-head column heads above a 2px ink rule, hairline rows, numbers right-aligned and bold. Inline bars are 8px tall: spot for the measured value, light tint for the track or stated value.

### Named Rules
**The Strike Weight Rule.** A miss is struck through, and the stroke weight is a linear function of the model's confidence in its wrong pick: 1px at 34% or below, rising to the context's maximum at 80% or above, rounded to the half pixel. Confident misses must be the heaviest marks on the page. Use the same scale everywhere a miss appears: mark grid, probability bar, verdict, prose.

**The Result Frame Rule.** The actual outcome is always marked by an ink frame on its segment, never by recoloring the segment.

## Do's and Don'ts

### Do:
- **Do** build every match view around the probability bar with its result frame, in home / draw / away order.
- **Do** strike every miss with the strike-weight scale (1px at 34%, maximum at 80%).
- **Do** open lists and tables with a 2px ink rule and separate rows with 1px hairlines.
- **Do** put a running head naming the volume at the top of every page.
- **Do** state the scoring mode and denominator next to every headline number ("68/104", "shootout-credited").
- **Do** set large record numbers in Archivo at 62% width, weight 850, line-height 0.85.
- **Do** keep dark mode as the same tokens reprinted on `dark-paper`, preserving the brightness order of spot, mid tint, light tint.

### Don't:
- **Don't** add a second hue: no red for misses, no green for hits.
- **Don't** use rounded corners, drop shadows, gradients, or paper textures.
- **Don't** wrap content in filled stat cards; use rules and tables.
- **Don't** show only the model's pick; show the three-way split.
- **Don't** use FIFA, federation, or tournament marks, crests, or trophy imagery.
- **Don't** use betting-coupon language or styling (odds, "lock", "banker", "value").
