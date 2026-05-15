# Data Visualization and Image Output Design

## 1. Overview
This design specifies the implementation of a data visualization module that converts scraped Yahoo Fantasy NBA data into grid-style table images. These images are designed to be sent via LINE Bot, requiring high readability on mobile devices.

## 2. Requirements & Layout

### 2.1 Stat Columns & Sorting
The image will display 11 stat categories horizontally in a single row:
1.  **FG**: Sorted by FG% (Descending)
2.  **FG%**: Sorted by FG% (Descending)
3.  **FT**: Sorted by FT% (Descending)
4.  **FT%**: Sorted by FT% (Descending)
5.  **3PT**: Sorted by Value (Descending)
6.  **PTS**: Sorted by Value (Descending)
7.  **REB**: Sorted by Value (Descending)
8.  **AST**: Sorted by Value (Descending)
9.  **ST**: Sorted by Value (Descending)
10. **BLK**: Sorted by Value (Descending)
11. **TO**: Sorted by Value (Ascending - Less is Better)

### 2.2 Visual Style
*   **Typography**: Use **Microsoft JhengHei** (微軟正黑體) for all text. Font size approx 13px.
*   **Color**: All text and borders must be **black**.
*   **Table Layout**: 
    *   Horizontal tight alignment for all 11 stat categories.
    *   **Thick Outside Borders**: Each stat category table has a **2px** outside border to distinguish categories.
    *   **Internal Borders**: 1px mesh grid inside each table.
    *   **Perfect Overlap**: Adjacent tables use `margin-left: -2px` to ensure shared 2px borders don't double in thickness.
    *   **Centered Content**: All text (player names and values) centered within cells.
    *   **Header**: Merged top row for category labels (e.g., "PTS"), centered and bold.
    *   **No Wrapping**: Ensure names and values do not wrap (`white-space: nowrap`).

### 2.3 Output Versions
1.  **Combined Version**: Daily stats row on top, Weekly stats row directly below. Separated by a simple **double horizontal line** (created by two 2px borders) with no text labels. Rows must be perfectly vertically aligned.
2.  **Separate Version**: Two independent images, one for Daily and one for Weekly.

### 2.4 Export Format
*   **Format**: PNG (preferred for line art and text clarity).
*   **Directory**: `data/images/`.

## 3. Architecture & Components

### 3.1 Data Processor (`src/visualizer/processor.py`)
*   Responsible for loading JSON data, performing the multi-criteria sorting, and preparing data structures for the template.

### 3.2 HTML Generator (`src/visualizer/renderer.py`)
*   Uses `Jinja2` to inject data into an HTML/CSS template that matches the confirmed visual design.

### 3.3 Image Capturer (`src/visualizer/capturer.py`)
*   Uses `Playwright` (headless browser) to render the HTML and take a precise screenshot of the table element.

## 4. Implementation Details
*   **Dependency Injection**: The visualizer will be triggered from `main.py` after data fetching is complete.
*   **Responsive Width**: Ensure the tables are sized appropriately for mobile screen viewing.

## 5. Testing
*   Verify sorting logic for all 11 categories (especially FG/FT/TO).
*   Verify image generation and file existence in `data/images/`.
*   Manual check of image quality and readability.
