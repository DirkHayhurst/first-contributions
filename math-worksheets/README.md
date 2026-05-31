# Math Worksheet Generator

Makes printable "All Operations" math worksheets: 100 mixed problems
(addition, subtraction, multiplication, division) in 4 columns, with a
matching answer key. Output is a self-contained HTML file — open it in any
browser and print, or "Save as PDF".

Problems stay kid-friendly: subtraction never goes negative, and division
always comes out to a whole number.

## Usage

```bash
python3 generate.py                  # one worksheet + answer key (100 problems)
python3 generate.py --sets 5         # five different worksheets at once
python3 generate.py --help           # all options
```

### Tuning difficulty

| Goal | Command |
|------|---------|
| Easier numbers, times-tables up to 5 | `python3 generate.py --max-factor 5 --max-add 10` |
| Multiplication & division only        | `python3 generate.py --ops x /` |
| Addition & subtraction only           | `python3 generate.py --ops + -` |
| Worksheet only, no answer key         | `python3 generate.py --no-key` |
| Reproduce the same worksheet          | `python3 generate.py --seed 42` |
| Fewer problems (e.g. 50)              | `python3 generate.py --count 50` |

Generated files are written to `output/` (git-ignored).

## Printing

Open the `.html` file in a browser, press **Ctrl/Cmd+P**, set margins to
"Default" or "None", and print or choose "Save as PDF". Page 1 is the
worksheet; page 2 is the answer key.
