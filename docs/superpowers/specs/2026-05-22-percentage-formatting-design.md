# Percentage Formatting Design Spec

## 1. Goal
Improve the readability of shooting percentages in the stats visualization by converting decimal values (e.g., 0.123) to a percentage format (e.g., 12.3%) with proper handling of zero values.

## 2. Requirements
- Target categories: `FG%` and `FT%`.
- Format: Multiplied by 100, rounded to one decimal place, followed by a `%` sign.
- Zero handling: If the value is `0` (resulting in `0.0%`), display `-` instead.
- Empty handling: If the value is missing or `None`, display `-`.

## 3. Implementation Details

### 3.1 Data Processing (`src/visualizer/processor.py`)
Modify `process_stats_for_visual` to include a formatting step for percentage-based keys.

**Transformation logic:**
```python
def format_percentage(val):
    try:
        num = float(val)
        if num == 0:
            return "-"
        return f"{num * 100:.1f}%"
    except (ValueError, TypeError):
        return "-"
```

### 3.2 Category Identification
The identification should rely on the `data_key` or a new flag in the category definition. Since `FG%` and `FT%` are standard, checking if the label or key contains `%` is sufficient.

## 4. Test Cases
| Input | Expected Output |
| :--- | :--- |
| `0.4567` | `"45.7%"` |
| `0.5` | `"50.0%"` |
| `0` | `"-"` |
| `None` | `"-"` |
| `"invalid"` | `"-"` |

## 5. Affected Files
- `src/visualizer/processor.py`
- `tests/test_visualizer_processor.py` (Add new tests)
