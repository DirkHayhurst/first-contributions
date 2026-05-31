# Math Worksheet Generator

Makes printable math worksheets with a matching answer key. Output is a
self-contained HTML file — open it in any browser and print, or "Save as PDF".
Page 1 is the worksheet; page 2 is the answer key.

Problems stay kid-friendly: subtraction never goes negative, division always
comes out to a whole number, and fraction answers stay proper.

## Styles

Pick a style with `--style`:

| Style | What it makes |
|-------|---------------|
| `horizontal` (default) | 100 mixed one-line problems (`+ - × ÷`) — the classic sheet |
| `stacked` | 3-digit addition & subtraction in vertical column form |
| `multiplication` | multi-step stacked multiplication (multi-digit × multi-digit) |
| `fractions` | add & subtract fractions that share the same denominator |
| `all` | one combined "combo platter" sheet with a labeled section of every type |

Every style lays out on a uniform fixed-cell grid, so stacking problems never
throws the rest of the page out of alignment. Stacked numbers are drawn in a
monospace box so the digit columns line up exactly.

## Usage

```bash
python3 generate.py                          # classic 100-problem mixed sheet
python3 generate.py --style stacked          # 3-digit stacked add/subtract
python3 generate.py --style multiplication   # multi-step stacked ×
python3 generate.py --style fractions        # same-denominator fraction +/-
python3 generate.py --style all              # combo sheet: a section of each type
python3 generate.py --sets 5                 # five different sheets at once
python3 generate.py --no-key                 # worksheet only, no answer key
python3 generate.py --help                   # all options
```

### Tuning difficulty

| Goal | Command |
|------|---------|
| Easier mixed numbers, times-tables up to 5 | `python3 generate.py --max-factor 5 --max-add 10` |
| Mixed sheet, addition & subtraction only    | `python3 generate.py --ops + -` |
| Stacked subtraction only                    | `python3 generate.py --style stacked --ops -` |
| 2-digit stacked add/subtract (easier)       | `python3 generate.py --style stacked --stack-min 10 --stack-max 99` |
| 3-digit × 1-digit multiplication (easier)   | `python3 generate.py --style multiplication --mult-bot-min 2 --mult-bot-max 9 --mult-top-min 100 --mult-top-max 999` |
| Fractions with denominators up to 8         | `python3 generate.py --style fractions --max-denom 8` |
| Worksheet only, no answer key               | `python3 generate.py --no-key` |
| Reproduce the same worksheet                | `python3 generate.py --seed 42` |
| Different number of problems                | `python3 generate.py --count 50` |

Generated files are written to `output/` (git-ignored).

## Printing

Open the `.html` file in a browser, press **Ctrl/Cmd+P**, set margins to
"Default" or "None", and print or choose "Save as PDF". Page 1 is the
worksheet; page 2 is the answer key.
