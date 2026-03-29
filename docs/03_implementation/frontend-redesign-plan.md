# Implementation Plan: Axiom Frontend Redesign

## 1. Overview

Full visual rewrite of the Axiom Canvas frontend to match the new design system defined in `design/axiom.pen`. The design file contains **21 screens** (1440x900 each) with a consistent layout pattern: 64px black sidebar + 52px PageTabHeader + content area. The current codebase already has most pages implemented with functional logic; this plan focuses on **visual alignment** with the new design while preserving existing API integrations and business logic.

### Key Technical Decisions

1. **Update tokens, not rebuild** -- The existing `tokens.css` already maps ~90% of the design variables. We update the remaining gaps (new status colors, text-placeholder, font mapping changes) rather than replacing the file.
2. **Refactor layout shell first** -- Sidebar and PageTabHeader are used by all 21 screens. Fixing them once propagates everywhere.
3. **Reuse existing feature slices** -- All 32 feature directories have functional hooks/api/store code. We rewrite only the `components/` and page files to match the design, keeping hooks and API layers untouched.
4. **New screens get new feature slices** -- Login already exists. Screens that lack feature directories (none identified) will use existing slices.
5. **Glass morphism stays** -- The design uses solid fills (`$--bg-card`, `$--bg-surface`), which aligns with the existing glass-card progressive enhancement approach.

---

## 2. Requirements Summary

### Functional Requirements
1. All 21 screens must visually match the `.pen` design file
2. Sidebar: 64px wide, black bg, 7 icon nav items (layout-dashboard, message-square-text, chart-bar, lightbulb, database, eye, settings), grouped with dividers, active state = left 3px orange/red border + white icon, inactive = gray icon
3. PageTabHeader: 52px height, 5 tabs (NL2SQL | OLAP Pivot | Insight | Ontology | Data), user avatar on right
4. Login: Split layout (560px brand panel on black bg + form panel)
5. Dashboard: 4 stat cards + Recent Cases table + Activity Timeline sidebar (280px)
6. Case List: Search + status filter + data table with column headers
7. Case Detail: Left/right split (main content + 300px Activity Panel)
8. All other screens follow their respective `.pen` layouts (see Section 4)
9. Dark mode support using existing `.dark` class toggle
10. i18n support (ko/en) for all new/modified text

### Non-Functional Requirements
1. Lazy loading for all page components (already in place via `lazyWithRetry`)
2. RBAC guards on all protected routes (already in place)
3. Responsive: mobile hamburger sidebar (already implemented), content areas fluid
4. Accessibility: skip-to-content link, focus indicators, ARIA labels (already in place)
5. Font loading: Sora (headings), Geist (body), JetBrains Mono (code), IBM Plex Mono (mono)

### Assumptions
- Backend APIs are stable and unchanged; only frontend visuals change
- The 5-tab PageTabHeader replaces the current 5-tab header (same tabs, same routes)
- Sidebar nav icon mappings: layout-dashboard=Dashboard, message-square-text=NL2SQL, chart-bar=OLAP, lightbulb=Insight, database=Data, eye=Watch, settings=Settings (bottom)
- Design uses `cornerRadius: 12` for cards, `8` for inputs/buttons, consistent spacing via `gap` and `padding`

---

## 3. Architecture Overview

### Current Architecture (preserved)
```
canvas/src/
  layouts/           <-- MODIFY: Sidebar, PageTabHeader, MainLayout
    components/      <-- MODIFY: PageTabHeader, UserMenu, ThemeToggle
  features/          <-- MODIFY: component files only, hooks/api/store untouched
    <name>/
      api/           (unchanged)
      hooks/         (unchanged)
      store/         (unchanged)
      types/         (unchanged)
      components/    <-- REWRITE to match design
  pages/             <-- REWRITE page shells to match design layouts
  styles/tokens.css  <-- UPDATE: add missing design variables
  index.css          <-- UPDATE: add design-specific utility classes
  components/ui/     <-- MAY ADD: new shadcn components as needed
  lib/routes/        (unchanged)
```

### Design-to-Code Mapping

| Design Variable | CSS Token | Status |
|----------------|-----------|--------|
| `$--primary` (#FF8400) | `--primary: 31 100% 50%` | EXISTS |
| `$--bg` (#FAFAFA) | `--background: 0 0% 98%` | EXISTS |
| `$--bg-card` (#FFFFFF) | `--card: 0 0% 100%` | EXISTS |
| `$--bg-sidebar` (#000000) | `--sidebar: 0 0% 0%` | EXISTS |
| `$--bg-surface` (#F5F5F5) | `--muted: 0 0% 96%` | EXISTS |
| `$--text-primary` (#000000) | `--foreground: 0 0% 7%` | CLOSE (7% vs 0%) |
| `$--text-secondary` (#5E5E5E) | `--muted-foreground: 0 0% 37%` | EXISTS |
| `$--text-tertiary` (#666666) | N/A | **ADD** |
| `$--text-placeholder` (#999999) | N/A | **ADD** |
| `$--text-on-dark` (#FAFAFA) | `--sidebar-foreground` | EXISTS |
| `$--accent-blue` (#3B82F6) | N/A (only in design) | **ADD** |
| `$--accent-green` (#22C55E) | `--success` | EXISTS |
| `$--accent-red` (#DC2626) | `--destructive` | EXISTS |
| `$--color-success` bg/fg | N/A | **ADD** |
| `$--color-warning` bg/fg | N/A | **ADD** |
| `$--color-error` bg/fg | N/A | **ADD** |
| `$--color-info` bg/fg | N/A | **ADD** |
| Font: Sora | `--font-heading` | EXISTS |
| Font: Geist | `--font-sans` | EXISTS |
| Font: JetBrains Mono | `--font-mono` | EXISTS |
| Font: IBM Plex Mono | `--font-mono` fallback | EXISTS |

---

## 4. Implementation Steps

### Phase 0: Design System Token Alignment (Day 1)
**Priority: CRITICAL -- blocks all other phases**

#### Step 0.1: Update CSS Design Tokens
- **What**: Add missing CSS variables to `tokens.css` and update mismatches
- **Where**: `canvas/src/styles/tokens.css`
- **How**: Add `--text-tertiary`, `--text-placeholder`, `--accent-blue`, status color pairs (success/warning/error/info bg + foreground). Update `--foreground` from `0 0% 7%` to `0 0% 0%` (pure black per design). Add dark mode equivalents.
- **Dependencies**: None
- **Validation**: Visual diff check -- all design colors reproducible via tokens
- **Complexity**: Low

#### Step 0.2: Update Tailwind Theme Mapping
- **What**: Map new CSS variables to Tailwind theme in `index.css`
- **Where**: `canvas/src/index.css`
- **How**: Add `--color-text-tertiary`, `--color-text-placeholder`, `--color-accent-blue`, `--color-status-*` to `@theme` block
- **Dependencies**: Step 0.1
- **Validation**: `className="text-text-tertiary"` works in JSX
- **Complexity**: Low

#### Step 0.3: Verify Font Loading
- **What**: Ensure Sora, Geist, JetBrains Mono, IBM Plex Mono are loaded
- **Where**: `canvas/index.html` or font import in CSS
- **How**: Check existing `@font-face` or Google Fonts imports. Add any missing fonts.
- **Dependencies**: None
- **Validation**: DevTools font inspector shows correct fonts applied
- **Complexity**: Low

**Phase 0 Total: ~3 files modified, 1 day**

---

### Phase 1: Layout Shell Rewrite (Days 2-3)
**Priority: CRITICAL -- all screens depend on the shell**

#### Step 1.1: Rewrite Sidebar
- **What**: Align Sidebar to design -- 64px wide, black bg, 7 icon items with exact lucide icons, grouped with dividers, active = left 3px orange border + white icon, settings at bottom
- **Where**: `canvas/src/layouts/Sidebar.tsx`
- **How**:
  - Keep existing `navGroups` structure but update to match design's 7 icons exactly:
    - Top group: `layout-dashboard` (Dashboard)
    - Analysis group: `message-square-text` (NL2SQL), `chart-bar` (OLAP), `lightbulb` (Insight)
    - Data group: `database` (Data/Sources)
    - Operations group: `eye` (Watch)
    - Bottom: `settings` (Settings)
  - Active indicator: change from `bg-destructive` to `bg-primary` (orange), keep 3px left border
  - Icon size: 18x18 (already correct)
  - Nav item height: 64px per item (design shows 64px per icon cell) -- currently 48px (`h-12`), change to `h-16`
  - Logo "A" at top in Sora 16px bold
  - Remove expanded groups that don't match design (currently 19 nav items, design shows only 7)
- **Design reference**: Node `jwdD8` -- Sidebar with `sideTop` (logo + 6 icons) and `sideBottom` (settings)
- **Dependencies**: Phase 0
- **Validation**: Screenshot comparison with design sidebar
- **Complexity**: Medium

**Key Decision -- Sidebar Simplification**: The design shows only 7 sidebar icons, but the current sidebar has 19 items across 4 groups. The remaining pages (Lineage, Glossary, Semantic Catalog, Domain Modeler, etc.) must be accessible via sub-navigation within the "Data" section or through the PageTabHeader. This requires a **sub-navigation pattern**: clicking the "database" icon either shows a dropdown/flyout with all data sub-pages, or the PageTabHeader tabs change contextually.

**Recommended approach**: Keep the sidebar at 7 icons matching the design. For pages not directly in the sidebar, use either:
- (A) The 5 top tabs in PageTabHeader route to top-level pages, and each top-level page has internal sub-tabs (e.g., Data page has tabs for Sources, Quality, Lineage, Glossary, etc.)
- (B) Sidebar icons expand a flyout panel with sub-items on hover/click

The design file's `PageTabHeader` consistently shows 5 tabs across all screens. I recommend approach (A) -- the sidebar serves as section-level navigation, and section-internal sub-navigation lives within each page's content area.

#### Step 1.2: Rewrite PageTabHeader
- **What**: Align header to design -- 52px height, 5 tabs, user avatar on right
- **Where**: `canvas/src/layouts/components/PageTabHeader.tsx`
- **How**:
  - Tabs: NL2SQL, OLAP Pivot, Insight, Ontology, Data (already correct)
  - Active tab: `text-foreground font-semibold` + bottom 2px red/orange border (currently `border-red-600`, change to `border-primary` or keep as `border-destructive`)
  - Inactive: `text-foreground/60` (matches current)
  - Font: Sora 13px (add `font-heading` class)
  - Height: 52px (already correct `h-[52px]`)
  - Padding: `px-48` (design shows `padding: [0, 48]`) -- currently `px-4 pl-14 md:pl-4 md:px-6 lg:px-12`, update to `px-12` (48px = 3rem)
  - Right side: 28x28 avatar circle (bg-surface), currently `<UserMenu />`
- **Design reference**: Node `gHREd` (NL2SQL header), `OTjrI` (Dashboard header)
- **Dependencies**: Phase 0
- **Validation**: Header matches design at 1440px width
- **Complexity**: Low

#### Step 1.3: Update MainLayout
- **What**: Minor adjustments to MainLayout flex container
- **Where**: `canvas/src/layouts/MainLayout.tsx`
- **How**: Already correct structure (`flex h-screen`). Verify no extra borders or spacing that differ from design.
- **Dependencies**: Steps 1.1, 1.2
- **Validation**: Empty content area matches design proportions
- **Complexity**: Low

**Phase 1 Total: ~3 files modified, 2 days**

---

### Phase 2: Login Screen Redesign (Day 4)
**Priority: HIGH -- first screen users see**

#### Step 2.1: Rewrite LoginPage
- **What**: Change from centered glass-card login to split-panel design
- **Where**: `canvas/src/pages/auth/LoginPage.tsx`
- **How**:
  - Left panel (560px): Black bg (`bg-sidebar`), centered vertically, contains:
    - "AXIOM" text: Sora 48px bold, letter-spacing -2, white
    - Tagline: Geist 18px, line-height 1.5, text-tertiary, centered, max-width 320px
    - Description: Geist 14px, text-placeholder, centered, max-width 320px
    - Padding: 64px all sides
  - Right panel (fill): White bg, centered vertically, contains:
    - "Sign in to Axiom": Sora 24px semibold, letter-spacing -0.5
    - Subtitle: Geist 14px, text-secondary
    - Email/Password fields: Geist 13px labels, 44px height inputs, cornerRadius 8, border
    - Sign In button: fill-width, 44px height, bg-primary, Geist 14px semibold, cornerRadius 8
    - Footer: Geist 12px, text-placeholder, centered
    - Form width: 400px, gap 24px between sections
    - Padding: 64px
  - Preserve all existing auth logic (useForm, onSubmit, test accounts, mock fallback)
  - Remove ambient gradient blobs and glass-card styling
- **Design reference**: Node `MrrII` -- Login frame
- **Dependencies**: Phase 0
- **Validation**: Side-by-side screenshot comparison
- **Complexity**: Medium

**Phase 2 Total: ~1 file rewritten, 1 day**

---

### Phase 3: Dashboard + Case Screens (Days 5-8)
**Priority: HIGH -- core workflow screens**

#### Step 3.1: Rewrite Dashboard Page
- **What**: Align CaseDashboardPage to design layout
- **Where**: `canvas/src/pages/dashboard/CaseDashboardPage.tsx`, `canvas/src/features/case-dashboard/components/`
- **How**:
  - Layout: Single column content body with padding `[32px, 48px]`
  - Stats Row: 4 cards in horizontal flex, gap 16, each card = `bg-card rounded-xl border p-5`, `fill_container` width
  - Bottom Row: 2-column flex (Recent Cases table `fill_container` + Activity Timeline 280px width), gap 24, `fill_container` height
  - Recent Cases card: `bg-card rounded-xl border`, full table inside
  - Activity Timeline card: `bg-card rounded-xl border`, scrollable list
  - **StatsCard** component: update to `cornerRadius: 12`, `gap: 8`, `padding: 20`, `border: 1px solid border`
  - **CaseTable**: keep TanStack Table logic, restyle to match design's col headers (bg-surface, h-40) and rows (h-44, bottom border)
  - **CaseTimeline**: restyle to fit 280px panel
- **Design reference**: Node `i8kML` -- Dashboard Main Content
- **Dependencies**: Phase 1
- **Validation**: 4 stat cards + table + timeline match design
- **Complexity**: Medium

#### Step 3.2: Rewrite Case List Page
- **What**: Align CaseListPage to design
- **Where**: `canvas/src/pages/cases/CaseListPage.tsx`
- **How**:
  - Content body: padding `[24px, 48px]`, gap 16, vertical layout
  - Filters row: Search input (280px, h-36, rounded-md, border) + Status dropdown (rounded-md, h-36) + count text (Geist 12px, text-secondary)
  - Cases Table: `bg-card rounded-xl border`, fill height
    - Col Headers: bg-surface, h-40, padding `[0, 20]`
    - Rows: h-44, padding `[0, 20]`, bottom border
  - Reuse existing `useCases` hook and filter logic
- **Design reference**: Node `bhlxS` -- Case List Main Content
- **Dependencies**: Phase 1
- **Validation**: Table columns, spacing, and filters match
- **Complexity**: Medium

#### Step 3.3: Rewrite Case Detail Page
- **What**: Align CaseDetailPage to split layout
- **Where**: `canvas/src/pages/cases/CaseDetailPage.tsx`
- **How**:
  - Body: horizontal flex, fill height
  - Left Column: padding `[24px, 32px]`, gap 24, fill width -- case info cards, documents, etc.
  - Activity Panel: 300px width, left border, padding `[24px, 20px]`, gap 16 -- activity feed
  - Preserve existing case detail hooks and API calls
- **Design reference**: Node `Tz1UW` -- Case Detail Main Content
- **Dependencies**: Phase 1
- **Validation**: Two-column layout matches
- **Complexity**: Medium

**Phase 3 Total: ~8-12 files modified, 4 days**

---

### Phase 4: Analysis Screens Redesign (Days 9-14)
**Priority: HIGH -- primary user-facing screens**

#### Step 4.1: Rewrite NL2SQL Page
- **What**: Align to design's 3-section content + right sidebar pattern
- **Where**: `canvas/src/pages/nl2sql/Nl2SqlPage.tsx`, `canvas/src/features/nl2sql/components/`
- **How**:
  - Content Column (fill): vertical layout
    - Title section: gap 8
    - Query section: gap 16 (SQL input, execute button)
    - Results section: gap 16 (result table/chart)
    - Padding: 48px
    - Gap between sections: 40px
  - Chat History panel (320px): right sidebar, left border
    - Header: "Query History" Sora 13px semibold, count badge (bg-surface, rounded)
    - Chat items: padding `[12px, 24px]`, gap 6 each, alternating bg-surface on active
  - Preserve existing NL2SQL hooks, chat logic, HIL flow
- **Design reference**: Nodes `4Qk5o`, `Y0s4q`, `OeekN`
- **Dependencies**: Phase 1
- **Validation**: Two-panel layout, chat sidebar width and styling
- **Complexity**: Medium

#### Step 4.2: Rewrite OLAP Pivot Page
- **What**: Align to design's dimension palette + pivot area layout
- **Where**: `canvas/src/pages/olap/OlapPivotPage.tsx`, `canvas/src/features/olap/components/`
- **How**:
  - Body: horizontal flex, fill height
  - Dimension Palette (220px): left panel, right border, padding `[16px, 12px]`, gap 12
  - Pivot Area (fill): padding `[16px, 20px]`, gap 16, vertical layout
  - Preserve existing OLAP pivot logic and drag-drop
- **Design reference**: Node `LiGCW` -- OLAP Pivot Main Content
- **Dependencies**: Phase 1
- **Validation**: Panel widths and spacing
- **Complexity**: Medium

#### Step 4.3: Rewrite Insight Page
- **What**: Align to design's KPI filter tabs + metrics cards + chart + detail panel
- **Where**: `canvas/src/pages/insight/InsightPage.tsx`, `canvas/src/features/insight/components/`
- **How**:
  - Content Column (fill): vertical, padding `[32px, 48px]`, gap 32
    - Title row: justify-between, title left + actions right
    - Filter row: "선택 KPI" label (IBM Plex Mono 11px, letter-spacing 1, text-placeholder) + tab filters (active = bottom 2px red border)
    - Metrics row: 3 cards, gap 16, each `padding [20, 24]`, border
    - Chart area: fill height, gap 16
  - Driver Detail panel (320px): right sidebar, left border
    - Header: 52px, padding `[0, 24]`, bottom border
    - Body: padding 24, gap 24
  - Preserve existing insight hooks (useInsightGraph, useDriverDetail, etc.)
- **Design reference**: Nodes `pcit7`, `JoGwX`, `ZNNJw`
- **Dependencies**: Phase 1
- **Validation**: 3-panel layout, filter tabs, metric cards
- **Complexity**: High

#### Step 4.4: Rewrite Ontology Page
- **What**: Align to design's filter row + graph canvas + detail panel
- **Where**: `canvas/src/pages/ontology/OntologyPage.tsx`, `canvas/src/features/ontology/components/`
- **How**:
  - Content Body: padding `[32px, 48px]`, gap 32
    - Title row: title + actions
    - Filter row: "Filter" label + layer filter tabs (All, Metric, KPI, Measure, Resource) with active = bottom 2px red
    - Graph + Detail: horizontal flex, fill height
      - Graph Canvas (fill): bg-surface, border, `layout: none` (absolute positioned nodes for Cytoscape)
      - Detail Panel (320px): border, vertical layout
  - Preserve existing Cytoscape graph logic
- **Design reference**: Nodes `soyF3`, `6is29`, `Av6dY`
- **Dependencies**: Phase 1
- **Validation**: Graph + detail panel layout
- **Complexity**: High

#### Step 4.5: Rewrite OLAP Studio Page
- **What**: Align to card-based model listing
- **Where**: `canvas/src/features/olap-studio/pages/OlapStudioPage.tsx`
- **How**:
  - Body: padding `[24px, 48px]`, gap 16
  - Model Cards row: horizontal flex, gap 16, fill width -- each card is a model summary
  - Preserve existing OLAP Studio hooks and API
- **Design reference**: Node `hJMqO` -- OLAP Studio Main Content
- **Dependencies**: Phase 1
- **Validation**: Card layout matches
- **Complexity**: Low

#### Step 4.6: Rewrite What-If Wizard Page
- **What**: Align to config panel + graph canvas layout
- **Where**: `canvas/src/pages/whatif/WhatIfWizardPage.tsx`, `canvas/src/features/whatif-wizard/components/`
- **How**:
  - Body: horizontal flex, padding `[32px, 48px]`, gap 32, fill height
  - Config Panel (360px): left side, vertical layout, gap 20
  - Graph Canvas (fill): bg-card, rounded-xl, border, centered content, padding 24
  - Preserve existing 9-step wizard logic
- **Design reference**: Node `vTxLu` -- What-If Wizard Main Content
- **Dependencies**: Phase 1
- **Validation**: Two-panel layout
- **Complexity**: Medium

**Phase 4 Total: ~20-30 files modified, 6 days**

---

### Phase 5: Data & Operations Screens (Days 15-20)
**Priority: MEDIUM -- supporting screens**

#### Step 5.1: Rewrite Data Sources Page
- **What**: Align to design layout
- **Where**: `canvas/src/pages/data/DatasourcePage.tsx`, `canvas/src/features/datasource/components/`
- **How**: Standard header + content body with ERD/table view. Preserve existing Mermaid ERD and schema canvas logic.
- **Design reference**: Node `O5I6P` -- Data Main Content
- **Dependencies**: Phase 1
- **Validation**: Layout matches
- **Complexity**: Medium

#### Step 5.2: Rewrite Semantic Catalog Page
- **What**: Align to table-based listing with search
- **Where**: `canvas/src/pages/semantic-catalog/SemanticCatalogPage.tsx`, `canvas/src/features/semantic-catalog/components/`
- **How**:
  - Body: padding `[24px, 32px]`, gap 16
  - Search row: gap 12, search input + filters
  - Table: bg-card, rounded-lg, border, with column headers and rows
  - Preserve existing 11-tab logic
- **Design reference**: Node `y6oS1` -- Semantic Catalog Main
- **Dependencies**: Phase 1
- **Validation**: Table styling matches
- **Complexity**: Medium

#### Step 5.3: Rewrite Data Quality Page
- **What**: Align to score cards + trust level + breaches layout
- **Where**: `canvas/src/pages/data/DataQualityPage.tsx`, `canvas/src/features/data-quality/components/`
- **How**:
  - Body: padding `[24px, 48px]`, gap 20, vertical layout
  - Score Cards row: horizontal flex
  - Trust Level: bg-card, rounded-xl, border, padding 20, gap 24, full width
  - Breaches: bg-card, rounded-xl, border, fill height, vertical layout
- **Design reference**: Node `kmo0I` -- Data Quality Main
- **Dependencies**: Phase 1
- **Validation**: Card and table layout
- **Complexity**: Medium

#### Step 5.4: Rewrite Domain Modeler Page
- **What**: Align to tree panel + model canvas split
- **Where**: `canvas/src/pages/domain/DomainModelerPage.tsx`, `canvas/src/features/domain-modeler/components/`
- **How**:
  - Body: horizontal flex, fill height
  - Tree Panel (260px): left side, right border, padding `[16px, 12px]`, gap 8
  - Model Canvas (fill): centered content, padding 24, gap 16
- **Design reference**: Node `VxtaX` -- Domain Modeler Main
- **Dependencies**: Phase 1
- **Validation**: Two-panel layout
- **Complexity**: Medium

#### Step 5.5: Rewrite Watch/Alerts Page
- **What**: Align to rules + event feed split
- **Where**: `canvas/src/pages/watch/WatchDashboardPage.tsx`, `canvas/src/features/watch/components/`
- **How**:
  - Body: horizontal flex, fill height
  - Rules panel (fill): padding `[24px, 32px]`, gap 16
  - Event Feed (360px): right side, left border, padding `[24px, 20px]`, gap 16
- **Design reference**: Node `IRwbI` -- Watch/Alerts Main
- **Dependencies**: Phase 1
- **Validation**: Two-panel layout
- **Complexity**: Medium

#### Step 5.6: Rewrite Process Designer Page
- **What**: Align to toolbar + canvas + properties triple-panel
- **Where**: `canvas/src/pages/process/ProcessDesignerPage.tsx`, `canvas/src/features/process-designer/components/`
- **How**:
  - Body: horizontal flex, fill height
  - Toolbar (56px): left side, bg-surface, right border, vertical icons, padding `[12px, 0]`
  - Canvas (fill): bg-bg, `layout: none` (Konva canvas)
  - Properties panel (260px): right side, left border, padding 16, gap 12
- **Design reference**: Node `8XdXu` -- Process Designer Main Content
- **Dependencies**: Phase 1
- **Validation**: Triple-panel layout
- **Complexity**: Medium

**Phase 5 Total: ~15-25 files modified, 6 days**

---

### Phase 6: Remaining Screens (Days 21-25)
**Priority: MEDIUM-LOW -- less frequently accessed screens**

#### Step 6.1: Rewrite Glossary Page
- **What**: Alphabet nav + terms table
- **Where**: `canvas/src/pages/data/GlossaryPage.tsx`, `canvas/src/features/glossary/components/`
- **How**:
  - Body: padding `[24px, 48px]`, gap 16
  - Alphabet row: horizontal flex, gap 4, letter buttons
  - Terms table: bg-card, rounded-xl, border, fill height
- **Design reference**: Node `mD4m2` -- Glossary Main
- **Dependencies**: Phase 1
- **Validation**: Alphabet bar + table
- **Complexity**: Low

#### Step 6.2: Rewrite Lineage Page
- **What**: DAG visualization with node cards
- **Where**: `canvas/src/pages/lineage/LineagePage.tsx`, `canvas/src/features/lineage/components/`
- **How**:
  - Body: `layout: none` (absolute positioned nodes)
  - Node cards: bg-card, rounded-lg, padding `[8px, 12px]`, colored borders (blue for source, orange for ETL, green for fact, gray for cube)
  - Legend: top-left, bg-card, border, padding `[12px, 16px]`
  - Connections drawn with SVG/Canvas lines
- **Design reference**: Node `6Qaan` -- Lineage Main (shows `layout: none` with positioned nodes)
- **Dependencies**: Phase 1
- **Validation**: Node positions and styling
- **Complexity**: High

#### Step 6.3: Rewrite Settings Page
- **What**: Left nav + content area split
- **Where**: `canvas/src/pages/settings/SettingsPage.tsx`
- **How**:
  - Body: horizontal flex, fill height
  - Settings Nav (220px): left side, right border, padding `[24px, 16px]`, gap 4
  - Settings Content (fill): padding `[32px, 48px]`, gap 24
  - Preserve existing sub-pages (System, Logs, Users, Config, Feedback, Security)
- **Design reference**: Node `mwA1Z` -- Settings Main
- **Dependencies**: Phase 1
- **Validation**: Two-panel navigation
- **Complexity**: Low

#### Step 6.4: Rewrite ETL Pipeline Page
- **What**: Pipeline cards layout
- **Where**: `canvas/src/features/olap-studio/pages/EtlPipelinesPage.tsx`
- **How**:
  - Body: padding `[24px, 48px]`, gap 16, vertical layout
  - Pipeline cards: full width, bg-card, rounded-xl, padding 20, gap 16, border (active = primary border 2px, inactive = regular border)
- **Design reference**: Node `Cp0yp` -- ETL Pipeline Main
- **Dependencies**: Phase 1
- **Validation**: Card styling
- **Complexity**: Low

#### Step 6.5: Rewrite Workflow Editor Page
- **What**: Steps panel + editor canvas split
- **Where**: `canvas/src/pages/workflow/WorkflowEditorPage.tsx`, `canvas/src/features/workflow-editor/components/`
- **How**:
  - Body: horizontal flex, fill height
  - Steps Panel (240px): left side, right border, padding `[16px, 12px]`, gap 12
  - Editor Canvas (fill): centered content, padding 32, gap 16
- **Design reference**: Node `vbITy` -- Workflow Editor Main
- **Dependencies**: Phase 1
- **Validation**: Two-panel layout
- **Complexity**: Medium

**Phase 6 Total: ~10-15 files modified, 5 days**

---

### Phase 7: Polish & Cross-Cutting (Days 26-28)
**Priority: HIGH -- quality gate**

#### Step 7.1: Dark Mode Verification
- **What**: Verify all 21 screens in dark mode
- **Where**: `canvas/src/styles/tokens.css` (`.dark` section)
- **How**: Systematically toggle dark mode on each screen, fix any missing/wrong dark tokens
- **Complexity**: Medium

#### Step 7.2: Responsive Breakpoints
- **What**: Verify mobile/tablet behavior
- **Where**: Various layout files
- **How**: Test at 768px and 375px breakpoints. Sidebar collapses (already implemented), content areas stack vertically where needed.
- **Complexity**: Medium

#### Step 7.3: i18n Key Audit
- **What**: Ensure all new text elements have i18n keys
- **Where**: `canvas/src/locales/` (ko.json, en.json)
- **How**: Grep for hardcoded strings in modified files, add missing translation keys
- **Complexity**: Low

#### Step 7.4: Accessibility Audit
- **What**: Verify ARIA labels, focus order, contrast ratios
- **Where**: All modified components
- **How**: Run axe-core, keyboard-navigate all screens, verify contrast with new color tokens
- **Complexity**: Medium

**Phase 7 Total: 3 days**

---

## 5. Files to Create/Modify

### Modified Files (by phase)

**Phase 0 -- Design Tokens**
| File | Change |
|------|--------|
| `src/styles/tokens.css` | Add ~12 new CSS variables, update 2 existing |
| `src/index.css` | Add ~8 new Tailwind theme mappings |
| `index.html` (if needed) | Add font imports |

**Phase 1 -- Layout Shell**
| File | Change |
|------|--------|
| `src/layouts/Sidebar.tsx` | Rewrite nav items to 7 icons, update sizing/active states |
| `src/layouts/components/PageTabHeader.tsx` | Update padding, font classes, active border color |
| `src/layouts/MainLayout.tsx` | Minor spacing tweaks |
| `src/layouts/components/UserMenu.tsx` | Update avatar size to 28x28 |

**Phase 2 -- Login**
| File | Change |
|------|--------|
| `src/pages/auth/LoginPage.tsx` | Full visual rewrite (split panel), logic preserved |

**Phase 3 -- Dashboard & Cases**
| File | Change |
|------|--------|
| `src/pages/dashboard/CaseDashboardPage.tsx` | Rewrite layout structure |
| `src/features/case-dashboard/components/StatsCard.tsx` | Update card styling |
| `src/features/case-dashboard/components/CaseTable.tsx` | Update table styling |
| `src/features/case-dashboard/components/CaseTimeline.tsx` | Restyle for 280px panel |
| `src/pages/cases/CaseListPage.tsx` | Rewrite to filter + table layout |
| `src/pages/cases/CaseDetailPage.tsx` | Rewrite to left/right split |

**Phase 4 -- Analysis (largest phase)**
| File | Change |
|------|--------|
| `src/pages/nl2sql/Nl2SqlPage.tsx` | Rewrite to content + chat sidebar |
| `src/features/nl2sql/components/*.tsx` | Update chat item, query input styling |
| `src/pages/olap/OlapPivotPage.tsx` | Rewrite to palette + pivot area |
| `src/features/olap/components/*.tsx` | Update dimension chips, pivot grid |
| `src/pages/insight/InsightPage.tsx` | Rewrite to filter tabs + metrics + chart + detail |
| `src/features/insight/components/*.tsx` | Update KPI cards, driver panels |
| `src/pages/ontology/OntologyPage.tsx` | Rewrite to filter + graph + detail |
| `src/features/ontology/components/*.tsx` | Update graph container, detail panel |
| `src/features/olap-studio/pages/OlapStudioPage.tsx` | Rewrite to card grid |
| `src/pages/whatif/WhatIfWizardPage.tsx` | Rewrite to config + graph |

**Phase 5 -- Data & Operations**
| File | Change |
|------|--------|
| `src/pages/data/DatasourcePage.tsx` | Update layout |
| `src/pages/semantic-catalog/SemanticCatalogPage.tsx` | Restyle table |
| `src/pages/data/DataQualityPage.tsx` | Rewrite to cards + breaches |
| `src/pages/domain/DomainModelerPage.tsx` | Rewrite to tree + canvas |
| `src/pages/watch/WatchDashboardPage.tsx` | Rewrite to rules + feed |
| `src/pages/process/ProcessDesignerPage.tsx` | Rewrite to toolbar + canvas + props |

**Phase 6 -- Remaining**
| File | Change |
|------|--------|
| `src/pages/data/GlossaryPage.tsx` | Rewrite to alphabet + table |
| `src/pages/lineage/LineagePage.tsx` | Restyle DAG nodes |
| `src/pages/settings/SettingsPage.tsx` | Rewrite to nav + content |
| `src/features/olap-studio/pages/EtlPipelinesPage.tsx` | Restyle pipeline cards |
| `src/pages/workflow/WorkflowEditorPage.tsx` | Rewrite to steps + canvas |

### New Files (minimal)
| File | Purpose |
|------|---------|
| `src/shared/components/PageContentLayout.tsx` | Optional: reusable content body wrapper with standard padding/gap |
| `src/shared/components/SplitLayout.tsx` | Optional: reusable main+sidebar layout (used by 8+ screens) |
| `src/shared/components/FilterTabBar.tsx` | Optional: reusable filter tab bar (used by Insight, Ontology, Case List) |

---

## 6. API Integration Points Per Screen

| Screen | Backend Service | Key Endpoints | Feature Hook |
|--------|----------------|---------------|-------------|
| Login | Core:9002 | `POST /api/v1/auth/login` | inline `axios.post` |
| Dashboard | Core:9002 | `GET /api/v1/cases`, `GET /api/v1/cases/activities` | `useCases`, `useCaseActivities`, `useCaseStats` |
| Case List | Core:9002 | `GET /api/v1/cases` | `useCases` |
| Case Detail | Core:9002 | `GET /api/v1/cases/:id`, `GET /api/v1/cases/:id/activities` | `useCase`, `useCaseActivities` |
| NL2SQL | Oracle:9004 | `POST /api/v3/oracle/ask`, `GET /api/v3/oracle/history` | `useNl2Sql`, `useQueryHistory` |
| OLAP Pivot | Vision:9100 | `POST /api/v1/vision/olap/pivot` | `useOlapPivot` |
| Insight | Vision:9100 | `POST /api/insight/impact`, `POST /api/insight/query-subgraph` | `useInsightGraph`, `useDriverDetail` |
| Ontology | Synapse:9003 | `GET /api/v3/synapse/ontology/*` | `useOntologyGraph`, `useOntologyDetail` |
| OLAP Studio | OLAP Studio:9005 | `GET /api/v1/olap-studio/models` | `useModels` |
| What-If Wizard | Vision:9100 | `POST /api/v1/vision/whatif/*` | `useWhatIfWizard` |
| Data Sources | Weaver:9001 | `GET /api/v1/weaver/datasources` | `useDatasources` |
| Semantic Catalog | Synapse:9003 | `GET /api/v3/synapse/semantic/*` | `useSemanticEntities` |
| Data Quality | Weaver:9001 | `GET /api/v1/weaver/quality/*` | `useQualityScores`, `useBreaches` |
| Domain Modeler | Synapse:9003 | `GET /api/v3/synapse/domain/*` | `useDomainTree` |
| Watch/Alerts | Core:9002 | `GET /api/v1/watch/rules`, `GET /api/v1/watch/alerts` | `useWatchRules`, `useWatchAlerts` |
| Process Designer | Core:9002 | `GET /api/v1/process/*` | `useProcessDefinitions` |
| Glossary | Weaver:9001 | `GET /api/v1/weaver/glossary` | `useGlossaryTerms` |
| Lineage | OLAP Studio:9005 | `GET /api/v1/olap-studio/lineage` | `useLineageGraph` |
| Settings | Core:9002 | `GET /api/v1/settings/*` | various settings hooks |
| ETL Pipeline | OLAP Studio:9005 | `GET /api/v1/olap-studio/etl/*` | `useEtlPipelines` |
| Workflow Editor | Core:9002 | `GET /api/v1/workflow/*` | `useWorkflowSteps` |

**No new API integrations required.** All hooks exist in their respective `features/<name>/hooks/` directories.

---

## 7. Testing Strategy

### Visual Regression
- Screenshot comparison for each of the 21 screens against the `.pen` design
- Check at 1440px (design target), 1024px (tablet), 375px (mobile)
- Light mode and dark mode for each screen

### Unit Tests
- No new unit tests needed for visual-only changes
- If any component logic changes (e.g., Sidebar nav item reduction), update existing tests

### Integration Tests
- Verify all routes still render without errors after layout changes
- Verify RBAC guards still function correctly
- Verify lazy loading still works for all pages

### Edge Cases
- Empty states (no data) for all table/list screens
- Loading states (skeletons) display correctly with new styling
- Error states render within new layout constraints
- Sidebar active state correctly highlights on all routes
- PageTabHeader active tab persists across navigation

---

## 8. Risk Assessment

### High Risk
1. **Sidebar simplification (19 items to 7)**: Users may lose quick access to frequently used pages. **Mitigation**: Ensure all pages remain accessible via sub-navigation within content areas. Consider a "more" flyout on the Database icon.
2. **Login page split-panel on mobile**: 560px brand panel won't fit on mobile. **Mitigation**: Stack panels vertically on mobile, hide brand panel or show condensed version.

### Medium Risk
3. **Font loading performance**: 4 font families = more network requests. **Mitigation**: Use `font-display: swap`, preload critical fonts (Geist for body text).
4. **Dark mode gaps**: New design variables may not have dark mode equivalents. **Mitigation**: Phase 0 includes dark mode token definitions; Phase 7 includes dark mode audit.
5. **Cytoscape/Konva canvas sizing**: Changing container dimensions may break canvas rendering. **Mitigation**: Test Ontology graph and Process Designer canvas early in their respective phases.

### Low Risk
6. **i18n key drift**: Hardcoded design text (e.g., "Query History") needs translation keys. **Mitigation**: Phase 7 i18n audit.
7. **Existing test breakage**: Snapshot tests or component tests may break from className changes. **Mitigation**: Update test snapshots after each phase.

---

## 9. Estimated Complexity Summary

| Phase | Screens | Files Modified | Days | Complexity |
|-------|---------|---------------|------|------------|
| 0: Design Tokens | -- | 2-3 | 1 | Low |
| 1: Layout Shell | -- | 3-4 | 2 | Medium |
| 2: Login | 1 | 1 | 1 | Medium |
| 3: Dashboard + Cases | 3 | 8-12 | 4 | Medium |
| 4: Analysis Screens | 6 | 20-30 | 6 | High |
| 5: Data & Operations | 6 | 15-25 | 6 | Medium |
| 6: Remaining Screens | 5 | 10-15 | 5 | Medium |
| 7: Polish | -- | various | 3 | Medium |
| **Total** | **21** | **~60-90** | **28 days** | |

### Dependency Graph
```
Phase 0 (Tokens)
  |
  v
Phase 1 (Layout Shell)
  |
  +---> Phase 2 (Login)         [independent]
  +---> Phase 3 (Dashboard/Cases) [independent]
  +---> Phase 4 (Analysis)       [independent]
  +---> Phase 5 (Data/Ops)       [independent]
  +---> Phase 6 (Remaining)      [independent]
  |
  v
Phase 7 (Polish)                [depends on all above]
```

Phases 2-6 can run **in parallel** after Phase 1 is complete. With 2+ developers, the total calendar time can be reduced to ~18-20 days.

---

## 10. Design Variable Reference (from axiom.pen)

```css
/* Primary Colors */
--primary: #FF8400          /* Orange -- buttons, active indicators */
--primary-foreground: #111111

/* Backgrounds */
--bg: #FAFAFA               /* Page background */
--bg-card: #FFFFFF           /* Card surfaces */
--bg-sidebar: #000000        /* Sidebar */
--bg-surface: #F5F5F5        /* Muted surfaces, table headers */

/* Text */
--text-primary: #000000      /* Headings, primary text */
--text-secondary: #5E5E5E    /* Secondary labels */
--text-tertiary: #666666     /* Inactive nav icons, subtle text */
--text-placeholder: #999999  /* Placeholder text, captions */
--text-on-dark: #FAFAFA      /* Text on dark backgrounds */

/* Accents */
--accent-blue: #3B82F6       /* Links, info states */
--accent-green: #22C55E      /* Success states */
--accent-red: #DC2626        /* Error, destructive actions */

/* Status (bg / foreground pairs) */
--color-success: #DFE6E1 / #004D1A
--color-warning: #E9E3D8 / #804200
--color-error: #E5DCDA / #8C1C00
--color-info: #DFDFE6 / #000066

/* Border */
--border: #E5E5E5            /* Default border */

/* Radii */
--radius-none: 0
--radius-m: 16               /* Not commonly used */
--radius-pill: 999

/* Standard component radii (from design inspection) */
Cards: cornerRadius 12
Inputs/Buttons: cornerRadius 8
Badges/Pills: cornerRadius 999

/* Fonts */
Sora: headings (font-heading)
Geist: body text (font-sans)
JetBrains Mono: code blocks (font-mono)
IBM Plex Mono: labels, captions (font-mono fallback)

/* Spacing (from design padding/gap patterns) */
Page padding: 48px (horizontal), 24-32px (vertical)
Card padding: 20px
Card gap: 8px internal
Section gap: 16-32px
Sidebar width: 64px
Header height: 52px
Nav icon cell: 64x64
Input height: 44px
Button height: 44px
Table header height: 40px
Table row height: 44px
```
