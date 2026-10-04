# Frontend Architecture & Technology Documentation
**Project:** AI-Based Resume Analyzer & Intelligent Candidate Ranking System (TalentLens)  
**Document Version:** 1.0  
**Scope:** Client-side interface, styling system, component breakdown, and runtime behavior  

---

## 1. Executive Summary & Design Philosophy

The frontend of **TalentLens** is engineered as a **zero-build, zero-dependency Single-Page Application (SPA)**. Instead of relying on heavy JavaScript frameworks (React, Angular, Vue) or complex Node.js build pipelines (Webpack, Vite, Babel), the entire user interface is constructed using standard web technologies:

- **HTML5 Semantic Markup** for clean document hierarchy and accessibility.
- **Modern Vanilla CSS3** utilizing CSS Custom Properties (variables), CSS Grid, Flexbox, and micro-animations.
- **Vanilla ECMAScript (ES6+)** for reactive DOM manipulation, drag-and-drop interactions, and asynchronous REST API integration.

### Core Design Principles
1. **Zero External Runtime Overhead:** Served directly by FastAPI's `StaticFiles` engine. No `npm install`, Node daemon, or bundler required.
2. **Modern SaaS Aesthetic:** Styled after contemporary recruiter platforms (Linear/Notion-inspired minimalist enterprise look) with soft ambient shadows, distinct typographic scale, and balanced whitespace.
3. **Instant Responsiveness:** Asynchronous event-driven updates with visual loading states, real-time file counters, and expandable candidate cards.
4. **Resilience & Security:** Client-side escaping of candidate data to prevent Cross-Site Scripting (XSS), alongside client-side file type and size validations.

---

## 2. Technology Stack & External Assets

| Category | Technology / Resource | Purpose |
| :--- | :--- | :--- |
| **Markup** | HTML5 | Semantic structure, input controls, accessibility attributes (`role="status"`, `aria-label`). |
| **Styling** | Vanilla CSS3 | Custom design system, responsive breakpoints, flex/grid layouts, animations. |
| **Scripting** | Vanilla JavaScript (ES6+) | State handling, asynchronous `fetch` calls, dynamic DOM rendering, drag-and-drop. |
| **Typography** | Google Fonts: `Manrope` & `DM Sans` | `Manrope` (weights 400-800) for sharp headings and numbers; `DM Sans` (weights 400-700) for readable body and inputs. |
| **Iconography** | Unicode Glyphs & Geometric CSS | Zero-latency symbols (`✳`, `♧`, `↗`, `▤`, `↑`, `→`, `⚙`, etc.) with zero network payload. |
| **Backend Integration** | RESTful Fetch API / FormData | Multipart file streaming (`/api/process`) and Form-encoded query requests (`/api/analyze`). |

---

## 3. Visual Design System & CSS Architecture (`styles.css`)

### 3.1 Design Tokens (CSS Custom Properties)
All global color schemes and shadows are centralized in the `:root` pseudo-class:

```css
:root {
  --ink: #192231;        /* Deep charcoal for primary text */
  --muted: #778295;      /* Slate grey for secondary captions and hints */
  --line: #e8ebf0;       /* Light border color for dividers and cards */
  --paper: #ffffff;      /* Pure white for card surfaces */
  --canvas: #f6f7f9;     /* Off-white background canvas */
  --blue: #4569e8;       /* Primary brand electric blue */
  --blue2: #edf1ff;      /* Pale blue tint for badges and active states */
  --green: #21a67a;      /* Emerald green for match indicators and success */
  --shadow: 0 5px 22px #26345108; /* Subtle elevation shadow */
}
```

### 3.2 Layout Model & Grid Systems
The interface employs a three-part layout structure:
1. **Fixed Sidebar (`244px` width):** Houses workspace identity, navigation links with active state pill indicators, support link, and recruiter user profile badge.
2. **Top Navigation Bar (`62px` height):** Features breadcrumb trails (`Workspace / Overview`) and notification triggers.
3. **Main Content Container:**
   - **Page Heading:** Greets user with dynamic visual hierarchy and the quick "Load demo candidates" action button.
   - **Metrics Grid (`stats-grid`):** A 4-column responsive grid (`repeat(4, 1fr)`) containing KPI cards with colored icon badges and unicode sparklines (`▁▂▂▃▂▄▅▆▅▇`).
   - **Dual-Panel Workspace (`content-grid`):** A two-column split layout (`minmax(390px, 0.92fr)` and `minmax(420px, 1.08fr)`):
     - **Left Panel (Upload & Query Configuration):** Manages step-by-step resume ingestion and job description input.
     - **Right Panel (Shortlist & Candidate Ranking):** Displays real-time ranking results and match telemetry.

### 3.3 Responsive Breakpoints
- **Desktop (> 1100px):** Full dual-column workspace with open sidebar and 4-column metric grid.
- **Tablet / Small Laptop (721px - 1100px):** Content grid collapses to a single vertical column (`grid-template-columns: 1fr`); stats grid adjusts to 2 columns (`repeat(2, 1fr)`).
- **Mobile Handheld (≤ 720px):**
  - Sidebar shrinks into a compact icon rail (`60px` width); text labels are hidden.
  - Page headings and actions stack vertically.
  - Content padding compresses to maximize screen real estate.

---

## 4. UI Components Breakdown (`index.html`)

### Component 1: Application Sidebar
- **Brand Identity:** Distinct geometric logo badge with `Manrope` logotype.
- **Workspace Selector:** Displays current tenant (`Acme Studio - Recruiting workspace`).
- **Navigation Groups:** Categorized under `WORKSPACE` and `MANAGE` with status count chips.
- **Recruiter Profile:** Avatar initials badge (`JD`), username, and permission role.

### Component 2: Analytics & Stat Cards
Displays four real-time project metrics:
1. **Total Candidates:** Current pool count in active session.
2. **Top Match Score:** Highest calculated match percentage from the latest ranking execution.
3. **Resumes Processed:** Successfully extracted PDF and DOCX files.
4. **Processing Issues:** Errors encountered during file parsing (empty files, unsupported formats).

### Component 3: Drag-and-Drop Resume Ingestion Dropzone
- Interactive file target accepting `.pdf` and `.docx` extensions.
- Hover and dragover states (`dragover` class) with active border coloring.
- Dynamic file listing displaying file type badges (`PDF` / `DOCX`), formatted file size in KB, and individual removal buttons (`×`).

### Component 4: Role Specification & Search Parameters
- **Job Title Field:** Input for role identification (e.g., "Machine Learning Engineer").
- **Top-K Selector:** Dropdown menu allowing selection of top 3, 5, or 10 candidates.
- **Job Description Textarea:** Live character counter updating dynamically on user keystrokes.
- **Action Buttons:** "Process resumes" and "Find top candidates" equipped with loading spinners and disabled state guards.

### Component 5: Shortlist Ranking Cards & Explanations
- **Rank Identifier:** Rounded two-digit badge (`01`, `02`, etc.).
- **Candidate Overview:** Resume filename, detected years of experience, and matched skill count.
- **Skill Chips:** Color-coded badges distinguishing matched skills (emerald green `#eaf7f1`) from missing skills (neutral grey `#f2f4f8`).
- **Match Score Display:** Prominent percentage fit score.
- **Expandable Detail Drawer (`candidate-details`):** Accordion trigger revealing:
  - 4-way score breakdown: Semantic %, Skill %, Experience %, Education %.
  - Matched skills list vs. missing skills list.
  - Education history & detected project titles.
  - Native `<details>` drawer containing the preprocessed normalized resume text.

---

## 5. JavaScript Implementation & Interaction Logic (`app.js`)

The JavaScript layer is lightweight (under 7 KB unminified) and handles client state, network communication, and DOM updates.

### 5.1 Helper Utilities
```javascript
// Quick DOM selector
const $ = s => document.querySelector(s);

// Client-side HTML entity escaping to neutralize XSS
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[c]));

// Percentage formatter
function pct(v) { return `${Math.round(v * 100)}%`; }
```

### 5.2 UI Feedback & Asynchronous State Guards
- `busy(button, on, label)`: Injects an animated CSS spinning wheel (`.spinner`) into the button, preserves previous button text in `data-label`, and toggles `disabled` to prevent double-submissions.
- `notice(message, ok)`: Updates the inline status alert bar with color coding (emerald green for success, coral red for errors).

### 5.3 Drag-and-Drop & File Queue Management
- Event listeners for `dragenter`, `dragover`, `dragleave`, and `drop` on `#dropzone`.
- File validation filters out unsupported extensions with a descriptive error.
- Deduplication prevents the exact same file from being added multiple times.
- Dynamically generates the selected file preview list with instant deletion buttons.

### 5.4 Backend API Communication
The frontend communicates with four FastAPI endpoints via the unified `api(url, options)` wrapper:

```javascript
async function api(url, options = {}) {
  const response = await fetch(url, options);
  let data;
  try {
    data = await response.json();
  } catch {
    data = { detail: 'The server returned an unexpected response.' };
  }
  if (!response.ok) throw new Error(data.detail || 'Request failed');
  return data;
}
```

1. **`GET /api/status`**: Polled on initial page load to synchronize dashboard stats with existing session candidates.
2. **`POST /api/process`**: Sends selected files via `multipart/form-data`. On success, updates counters, clears the upload queue, and enables role analysis.
3. **`POST /api/demo`**: Requests the backend to ingest the pre-packaged demo resumes from `sample_data/resumes`.
4. **`POST /api/analyze`**: Dispatches `title`, `job_description`, and `top_k` as `FormData`. Parses returned ranked candidates and invokes `renderResults()`.

### 5.5 Dynamic Results Rendering & Interactive Accordion
`renderResults(title)` dynamically creates candidate cards using template literals:
- Assigns matched skill chips (up to 4 visible) and missing skill chips (up to 2 visible).
- Attaches click event handlers to `.candidate-row` items to toggle `.open` on `#detail-${index}`, smoothly showing or hiding the comprehensive score breakdown.

---

## 6. Summary of Strengths & Architectural Merits

1. **Zero Compilation Friction:** No `node_modules` folder, no version mismatches, and no vulnerability warnings from third-party npm packages.
2. **Extreme Speed & Low Footprint:** Total frontend assets amount to less than 25 KB of HTML, CSS, and JS combined.
3. **High Transparency & Recruiter Explainability:** Unlike black-box scoring systems, the frontend explicitly visualizes why a candidate received their score (semantic similarity vs. specific skill gaps).
4. **Clean Decoupling:** The UI interacts with the backend strictly through JSON REST contracts, enabling the backend to be upgraded or swapped without breaking the presentation layer.
