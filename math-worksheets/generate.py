#!/usr/bin/env python3
"""
Math worksheet generator.

Makes printable "All Operations" worksheets like the ones from school:
100 mixed problems (addition, subtraction, multiplication, division)
laid out in 4 columns, plus a matching answer key.

Output is a self-contained HTML file. Open it in any browser and print
(or "Save as PDF"). It is sized to fit a single page.

Examples
--------
    # one worksheet + answer key with defaults (100 problems)
    python3 generate.py

    # make 5 different worksheets at once
    python3 generate.py --sets 5

    # easier numbers, multiplication tables up to 5
    python3 generate.py --max-factor 5 --max-add 10

    # only multiplication and division practice
    python3 generate.py --ops x /

    # reproduce the exact same worksheet again
    python3 generate.py --seed 42
"""

import argparse
import random
import os
from datetime import date

# ----------------------------------------------------------------------
# Problem generation
# ----------------------------------------------------------------------

def make_addition(rng, max_add):
    a = rng.randint(0, max_add)
    b = rng.randint(0, max_add)
    return f"{a} + {b} =", a + b


def make_subtraction(rng, max_sub):
    # keep the answer >= 0 (no negative numbers for young learners)
    a = rng.randint(0, max_sub)
    b = rng.randint(0, a)
    return f"{a} - {b} =", a - b


def make_multiplication(rng, max_factor):
    a = rng.randint(0, max_factor)
    b = rng.randint(0, max_factor)
    return f"{a} × {b} =", a * b


def make_division(rng, max_factor):
    # build from a known product so the answer is always a whole number
    divisor = rng.randint(1, max_factor)
    quotient = rng.randint(0, max_factor)
    dividend = divisor * quotient
    return f"{dividend} ÷ {divisor} =", quotient


GENERATORS = {
    "+": lambda rng, a: make_addition(rng, a.max_add),
    "-": lambda rng, a: make_subtraction(rng, a.max_sub),
    "x": lambda rng, a: make_multiplication(rng, a.max_factor),
    "/": lambda rng, a: make_division(rng, a.max_factor),
}


def build_problems(rng, args):
    """Return a list of (problem_text, answer) tuples."""
    problems = []
    for _ in range(args.count):
        op = rng.choice(args.ops)
        problems.append(GENERATORS[op](rng, args))
    return problems


# ----------------------------------------------------------------------
# HTML rendering
# ----------------------------------------------------------------------

PAGE_CSS = """
* { box-sizing: border-box; }
body { font-family: Georgia, 'Times New Roman', serif; margin: 0; color: #111; }
.page {
    width: 8.5in; min-height: 11in; padding: 0.6in 0.7in; margin: 0 auto;
    page-break-after: always;
}
.page:last-child { page-break-after: auto; }
.title-box {
    border: 2px solid #111; padding: 8px 12px; text-align: center;
    font-size: 20px; font-weight: bold; letter-spacing: 0.5px;
}
.subtitle { text-align: center; font-size: 15px; margin: 10px 0 4px; }
.meta {
    display: flex; justify-content: space-between;
    font-size: 13px; margin: 6px 2px 16px; color: #333;
}
.grid {
    display: grid; grid-template-columns: repeat(4, 1fr);
    grid-auto-flow: column; gap: 6px 18px;
}
.cell {
    font-size: 17px; padding: 4px 2px; white-space: nowrap;
    display: flex; align-items: baseline;
}
.num { display: inline-block; width: 26px; color: #555; font-size: 13px; }
.prob { font-variant-numeric: tabular-nums; }
.ans { color: #c0392b; font-weight: bold; margin-left: 4px; }
.key-tag { color: #c0392b; }
@media print {
    .no-print { display: none; }
    body { margin: 0; }
}
.no-print {
    background: #f4f4f4; border: 1px solid #ccc; padding: 10px 14px;
    font-family: -apple-system, system-ui, sans-serif; font-size: 13px;
    max-width: 8.5in; margin: 12px auto;
}
"""

def render_page(problems, title, subtitle, label, show_answers, rows):
    cells = []
    for i, (text, ans) in enumerate(problems, 1):
        ans_html = f'<span class="ans">{ans}</span>' if show_answers else ""
        cells.append(
            f'<div class="cell"><span class="num">{i}.</span>'
            f'<span class="prob">{text}</span>{ans_html}</div>'
        )
    grid_style = f"grid-template-rows: repeat({rows}, auto);"
    return f"""
    <div class="page">
        <div class="title-box">{title}{label}</div>
        <div class="subtitle">{subtitle}</div>
        <div class="meta">
            <span>Name: ______________________</span>
            <span>Date: ______________</span>
            <span>Score: _____ / {len(problems)}</span>
        </div>
        <div class="grid" style="{grid_style}">
            {''.join(cells)}
        </div>
    </div>
    """


def render_document(problems, args):
    rows = -(-args.count // 4)  # ceil division -> rows per column (4 columns)
    pages = [render_page(
        problems, args.title, args.subtitle, "", False, rows)]
    if not args.no_key:
        pages.append(render_page(
            problems, args.title,
            "Answer Key", ' <span class="key-tag">(KEY)</span>', True, rows))
    help_banner = (
        '<div class="no-print">'
        '<b>To print:</b> Press Ctrl/Cmd+P, set margins to "Default" or "None", '
        'and choose your printer or "Save as PDF". This banner will not appear '
        'on the printout.</div>'
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{args.title}</title>
<style>{PAGE_CSS}</style>
</head>
<body>
{help_banner}
{''.join(pages)}
</body>
</html>
"""


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Generate printable mixed-operations math worksheets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    p.add_argument("--count", type=int, default=100,
                   help="problems per worksheet (default: 100)")
    p.add_argument("--sets", type=int, default=1,
                   help="number of different worksheets to make (default: 1)")
    p.add_argument("--ops", nargs="+", default=["+", "-", "x", "/"],
                   choices=["+", "-", "x", "/"],
                   help="operations to include (default: + - x /)")
    p.add_argument("--max-factor", type=int, default=10,
                   help="largest factor/divisor for x and / (default: 10)")
    p.add_argument("--max-add", type=int, default=20,
                   help="largest number used in addition (default: 20)")
    p.add_argument("--max-sub", type=int, default=20,
                   help="largest number used in subtraction (default: 20)")
    p.add_argument("--seed", type=int, default=None,
                   help="random seed for reproducible worksheets")
    p.add_argument("--no-key", action="store_true",
                   help="do not include the answer key page")
    p.add_argument("--title", default="All Operations",
                   help='worksheet title (default: "All Operations")')
    p.add_argument("--subtitle",
                   default="Calculate each sum, difference, product, or quotient.",
                   help="instruction line under the title")
    p.add_argument("--outdir", default=os.path.join(
                   os.path.dirname(os.path.abspath(__file__)), "output"),
                   help="where to write the .html files")
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    base_seed = args.seed if args.seed is not None else random.randrange(1 << 30)
    stamp = date.today().isoformat()

    written = []
    for n in range(1, args.sets + 1):
        rng = random.Random(base_seed + n)
        problems = build_problems(rng, args)
        html = render_document(problems, args)
        suffix = f"-{n}" if args.sets > 1 else ""
        path = os.path.join(args.outdir, f"worksheet-{stamp}{suffix}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        written.append(path)

    print(f"Created {len(written)} worksheet(s):")
    for path in written:
        print(f"  {path}")
    print("\nOpen any file in a web browser and print (or Save as PDF).")
    print(f"Seed: {base_seed}  (reuse with --seed {base_seed} to reproduce)")


if __name__ == "__main__":
    main()
