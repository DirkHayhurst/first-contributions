#!/usr/bin/env python3
"""
Math worksheet generator.

Makes printable math worksheets like the ones from school, in four styles:

  horizontal     100 mixed one-line problems (+, -, x, /) -- the classic sheet
  stacked        3-digit addition & subtraction in vertical column form
  multiplication multi-step stacked multiplication (multi-digit x multi-digit)
  fractions      add & subtract fractions that share the same denominator

Every style lays out on a uniform fixed-cell grid, so stacking problems never
throws the rest of the page out of alignment. Stacked numbers are drawn in a
monospace box with space-padding, so the digit columns line up exactly.

Output is a self-contained HTML file. Open it in any browser and print
(or "Save as PDF"). Page 1 is the worksheet; page 2 is the answer key.

Examples
--------
    python3 generate.py                          # classic 100-problem mixed sheet
    python3 generate.py --style stacked          # 3-digit stacked add/subtract
    python3 generate.py --style multiplication   # multi-step stacked x
    python3 generate.py --style fractions        # same-denominator fraction +/-
    python3 generate.py --style stacked --sets 5 # five different sheets at once
    python3 generate.py --style stacked --ops -  # subtraction only
    python3 generate.py --seed 42                # reproduce an exact sheet
"""

import argparse
import copy
import random
import os
from datetime import date

MULT = "×"   # ×
DIV = "÷"    # ÷


# ----------------------------------------------------------------------
# Problem generation
# ----------------------------------------------------------------------
# Every problem is a dict with a "kind" the renderer knows how to draw:
#   {"kind": "h",     "text": "15 - 8 =", "answer": 7}
#   {"kind": "stack", "a": 472, "b": 135, "op": "+", "answer": 607, "work": False}
#   {"kind": "frac",  "n1": 3, "n2": 2, "d": 8, "op": "+", "ans_num": 5}

def gen_horizontal(rng, args):
    op = rng.choice(args.ops)
    if op == "+":
        a, b = rng.randint(0, args.max_add), rng.randint(0, args.max_add)
        return {"kind": "h", "text": f"{a} + {b} =", "answer": a + b}
    if op == "-":
        a = rng.randint(0, args.max_sub)
        b = rng.randint(0, a)
        return {"kind": "h", "text": f"{a} - {b} =", "answer": a - b}
    if op == "x":
        a, b = rng.randint(0, args.max_factor), rng.randint(0, args.max_factor)
        return {"kind": "h", "text": f"{a} {MULT} {b} =", "answer": a * b}
    # division -- build from a known product so the answer is whole
    divisor = rng.randint(1, args.max_factor)
    quotient = rng.randint(0, args.max_factor)
    return {"kind": "h", "text": f"{divisor * quotient} {DIV} {divisor} =",
            "answer": quotient}


def gen_stacked(rng, args):
    """3-digit (configurable) addition / subtraction, vertical form."""
    op = rng.choice(args.ops)
    if op == "+":
        a = rng.randint(args.stack_min, args.stack_max)
        b = rng.randint(args.stack_min, args.stack_max)
        return {"kind": "stack", "a": a, "b": b, "op": "+",
                "answer": a + b, "work": False}
    # subtraction -- keep the answer >= 0, both operands in range
    a = rng.randint(args.stack_min, args.stack_max)
    b = rng.randint(args.stack_min, a)
    return {"kind": "stack", "a": a, "b": b, "op": "-",
            "answer": a - b, "work": False}


def gen_multiplication(rng, args):
    """Multi-step stacked multiplication (multi-digit x multi-digit)."""
    a = rng.randint(args.mult_top_min, args.mult_top_max)
    b = rng.randint(args.mult_bot_min, args.mult_bot_max)
    return {"kind": "stack", "a": a, "b": b, "op": MULT,
            "answer": a * b, "work": True}


def gen_fraction(rng, args):
    """Add/subtract two fractions with the same denominator. Proper results."""
    op = rng.choice(args.ops)
    d = rng.randint(2, args.max_denom)
    if op == "+":
        # keep the sum proper: n1 + n2 <= d
        n1 = rng.randint(1, d - 1)
        n2 = rng.randint(1, d - n1)
        return {"kind": "frac", "n1": n1, "n2": n2, "d": d, "op": "+",
                "ans_num": n1 + n2}
    # subtraction -- keep result >= 0
    n1 = rng.randint(1, d - 1)
    n2 = rng.randint(1, n1)
    return {"kind": "frac", "n1": n1, "n2": n2, "d": d, "op": "-",
            "ans_num": n1 - n2}


STYLES = {
    "horizontal":     gen_horizontal,
    "stacked":        gen_stacked,
    "multiplication": gen_multiplication,
    "fractions":      gen_fraction,
}

# operations each style is allowed to use (multiplication is fixed to x)
ALLOWED_OPS = {
    "horizontal":     ["+", "-", "x", "/"],
    "stacked":        ["+", "-"],
    "multiplication": ["x"],
    "fractions":      ["+", "-"],
}

# per-style defaults: (problem count, grid columns, title, subtitle)
DEFAULTS = {
    "horizontal": (100, 4, "All Operations",
                   "Calculate each sum, difference, product, or quotient."),
    "stacked": (24, 6, "Three-Digit Addition & Subtraction",
                "Add or subtract. Line up the digits and regroup as needed."),
    "multiplication": (15, 5, "Stacked Multiplication",
                       "Multiply. Show your partial products and add them up."),
    "fractions": (20, 4, "Fractions: Add & Subtract",
                  "Add or subtract. Keep the same denominator."),
    # the "combo platter": one sheet with a labeled section of every type
    "all": (None, None, "Mixed Math Practice",
            "Solve each problem. Show your work where you need to."),
}
ALLOWED_OPS["all"] = ["+", "-", "x", "/"]

# sections for the "all" style: (heading, style, problem count, grid columns)
ALL_SECTIONS = [
    ("Part A — Add, Subtract, Multiply &amp; Divide", "horizontal", 16, 4),
    ("Part B — Three-Digit Addition &amp; Subtraction", "stacked", 8, 4),
    ("Part C — Multiplication", "multiplication", 4, 4),
    ("Part D — Fractions (same denominator)", "fractions", 8, 4),
]


def build_problems(rng, args):
    gen = STYLES[args.style]
    return [gen(rng, args) for _ in range(args.count)]


# ----------------------------------------------------------------------
# HTML rendering
# ----------------------------------------------------------------------

PAGE_CSS = """
* { box-sizing: border-box; }
body { font-family: Georgia, 'Times New Roman', serif; margin: 0; color: #111; }
.page {
    width: 8.5in; min-height: 11in; padding: 0.55in 0.65in; margin: 0 auto;
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

/* Uniform grid: column-major fill so problems number down each column.
   Fixed rows + per-style cell min-heights keep everything aligned. */
.grid {
    display: grid; grid-auto-flow: column; gap: 10px 16px;
}
.cell {
    display: flex; align-items: flex-start; gap: 6px;
    font-size: 17px; padding: 2px;
}
.qnum { color: #666; font-size: 13px; min-width: 24px; text-align: right;
        padding-top: 2px; }
.prob { font-variant-numeric: tabular-nums; }

/* horizontal style */
.cell.h { white-space: nowrap; }

/* stacked add/sub & multiplication share the monospace box */
.cell.stack { min-height: 78px; }
.cell.stack.work { min-height: 120px; }   /* extra room for partial products */
.stack-wrap { display: inline-block; }
.stack-nums {
    margin: 0; font-family: 'Courier New', Courier, monospace;
    font-size: 19px; line-height: 1.3;
    border-bottom: 2px solid #111; padding-bottom: 2px;
}
.ans-slot {
    margin: 0; font-family: 'Courier New', Courier, monospace;
    font-size: 19px; line-height: 1.3; min-height: 1.3em;
    color: #c0392b; font-weight: bold;
}

/* fractions */
.cell.frac { align-items: center; min-height: 70px; }
.fr { display: inline-flex; flex-direction: column; align-items: center;
      margin: 0 4px; line-height: 1.05; }
.fr .top { border-bottom: 2px solid #111; padding: 0 6px; }
.fr .bot { padding: 0 6px; }
.op, .eq { margin: 0 5px; }
.ans-frac.blank {
    display: inline-block; width: 34px; border-bottom: 1px solid #888;
    margin-left: 6px;
}
.ans-frac .fr { color: #c0392b; }
.ans-frac .fr .top { border-color: #c0392b; }

/* section headings on the combined "all" sheet */
.section-title {
    font-size: 15px; font-weight: bold; margin: 14px 0 6px;
    border-bottom: 1px solid #999; padding-bottom: 3px;
}

.key-tag { color: #c0392b; }
@media print { .no-print { display: none; } body { margin: 0; } }
.no-print {
    background: #f4f4f4; border: 1px solid #ccc; padding: 10px 14px;
    font-family: -apple-system, system-ui, sans-serif; font-size: 13px;
    max-width: 8.5in; margin: 12px auto;
}
"""


def render_horizontal(p, show):
    ans = f' <span style="color:#c0392b;font-weight:bold">{p["answer"]}</span>' if show else ""
    return f'<span class="prob">{p["text"]}</span>{ans}'


def render_stack(p, show):
    a, b, op, ans = p["a"], p["b"], p["op"], p["answer"]
    field = max(len(str(a)), len(str(b)), len(str(ans)))
    top = f"  {str(a).rjust(field)}"        # 2 cols reserved for the operator
    bot = f"{op} {str(b).rjust(field)}"
    ans_line = f"  {str(ans).rjust(field)}" if show else ""
    return (
        '<div class="stack-wrap">'
        f'<pre class="stack-nums">{top}\n{bot}</pre>'
        f'<pre class="ans-slot">{ans_line}</pre>'
        '</div>'
    )


def _fr(num, den):
    return f'<span class="fr"><span class="top">{num}</span><span class="bot">{den}</span></span>'


def render_frac(p, show):
    op_sym = "+" if p["op"] == "+" else "−"  # − minus sign
    left = _fr(p["n1"], p["d"])
    right = _fr(p["n2"], p["d"])
    if show:
        answer = f'<span class="ans-frac">{_fr(p["ans_num"], p["d"])}</span>'
    else:
        answer = '<span class="ans-frac blank"></span>'
    return (f'{left}<span class="op">{op_sym}</span>{right}'
            f'<span class="eq">=</span>{answer}')


RENDERERS = {"h": render_horizontal, "stack": render_stack, "frac": render_frac}


def render_cell(p, index, show):
    body = RENDERERS[p["kind"]](p, show)
    cls = p["kind"]
    if p["kind"] == "stack" and p.get("work"):
        cls += " work"
    return f'<div class="cell {cls}"><span class="qnum">{index}.</span>{body}</div>'


def render_page(problems, args, label, show):
    rows = -(-args.count // args.columns)  # ceil -> rows per column
    cells = "".join(render_cell(p, i, show) for i, p in enumerate(problems, 1))
    grid_style = (f"grid-template-columns: repeat({args.columns}, 1fr);"
                  f"grid-template-rows: repeat({rows}, auto);")
    return f"""
    <div class="page">
        <div class="title-box">{args.title}{label}</div>
        <div class="subtitle">{args.subtitle if not show else 'Answer Key'}</div>
        <div class="meta">
            <span>Name: ______________________</span>
            <span>Date: ______________</span>
            <span>Score: _____ / {len(problems)}</span>
        </div>
        <div class="grid" style="{grid_style}">{cells}</div>
    </div>
    """


def wrap_html(title, pages):
    banner = (
        '<div class="no-print"><b>To print:</b> Press Ctrl/Cmd+P, set margins '
        'to "Default" or "None", then print or "Save as PDF". This banner will '
        'not appear on the printout.</div>'
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{PAGE_CSS}</style></head>
<body>{banner}{''.join(pages)}</body></html>
"""


def render_document(problems, args):
    pages = [render_page(problems, args, "", False)]
    if not args.no_key:
        pages.append(render_page(
            problems, args, ' <span class="key-tag">(KEY)</span>', True))
    return wrap_html(args.title, pages)


# --- combined "all" sheet: a labeled section of every problem type ----------

def build_all_sections(rng, args):
    """Return [(heading, [problems], columns), ...] for the combo sheet."""
    sections = []
    for heading, style, count, cols in ALL_SECTIONS:
        sec = copy.copy(args)
        sec.style = style
        sec.ops = ALLOWED_OPS[style]
        gen = STYLES[style]
        sections.append((heading, [gen(rng, sec) for _ in range(count)], cols))
    return sections


def render_section(heading, problems, columns, show):
    rows = -(-len(problems) // columns)
    cells = "".join(render_cell(p, i, show) for i, p in enumerate(problems, 1))
    grid_style = (f"grid-template-columns: repeat({columns}, 1fr);"
                  f"grid-template-rows: repeat({rows}, auto);")
    return (f'<div class="section-title">{heading}</div>'
            f'<div class="grid" style="{grid_style}">{cells}</div>')


def render_all_page(sections, args, label, show):
    total = sum(len(p) for _, p, _ in sections)
    body = "".join(render_section(h, p, c, show) for h, p, c in sections)
    subtitle = "Answer Key" if show else args.subtitle
    return f"""
    <div class="page">
        <div class="title-box">{args.title}{label}</div>
        <div class="subtitle">{subtitle}</div>
        <div class="meta">
            <span>Name: ______________________</span>
            <span>Date: ______________</span>
            <span>Score: _____ / {total}</span>
        </div>
        {body}
    </div>
    """


def render_all_document(sections, args):
    pages = [render_all_page(sections, args, "", False)]
    if not args.no_key:
        pages.append(render_all_page(
            sections, args, ' <span class="key-tag">(KEY)</span>', True))
    return wrap_html(args.title, pages)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Generate printable math worksheets in several styles.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--style", choices=list(STYLES) + ["all"],
                   default="horizontal",
                   help="worksheet style, or 'all' for a combined sheet with a "
                        "section of every type (default: horizontal)")
    p.add_argument("--count", type=int, default=None,
                   help="problems per worksheet (default depends on style)")
    p.add_argument("--columns", type=int, default=None,
                   help="grid columns (default depends on style)")
    p.add_argument("--sets", type=int, default=1,
                   help="number of different worksheets to make (default: 1)")
    p.add_argument("--ops", nargs="+", default=None,
                   choices=["+", "-", "x", "/"],
                   help="operations to include (filtered to those the style "
                        "supports; default: all the style allows)")
    p.add_argument("--seed", type=int, default=None,
                   help="random seed for reproducible worksheets")
    p.add_argument("--no-key", action="store_true",
                   help="do not include the answer-key page")
    p.add_argument("--title", default=None, help="override the worksheet title")
    p.add_argument("--subtitle", default=None,
                   help="override the instruction line")
    # horizontal ranges
    p.add_argument("--max-factor", type=int, default=10,
                   help="largest factor/divisor for horizontal x and / (10)")
    p.add_argument("--max-add", type=int, default=20,
                   help="largest number used in horizontal addition (20)")
    p.add_argument("--max-sub", type=int, default=20,
                   help="largest number used in horizontal subtraction (20)")
    # stacked add/sub ranges
    p.add_argument("--stack-min", type=int, default=100,
                   help="smallest operand for stacked add/sub (100)")
    p.add_argument("--stack-max", type=int, default=999,
                   help="largest operand for stacked add/sub (999)")
    # stacked multiplication ranges
    p.add_argument("--mult-top-min", type=int, default=12,
                   help="smallest top factor for stacked multiplication (12)")
    p.add_argument("--mult-top-max", type=int, default=99,
                   help="largest top factor for stacked multiplication (99)")
    p.add_argument("--mult-bot-min", type=int, default=12,
                   help="smallest bottom factor for stacked multiplication (12)")
    p.add_argument("--mult-bot-max", type=int, default=99,
                   help="largest bottom factor for stacked multiplication (99)")
    # fractions
    p.add_argument("--max-denom", type=int, default=12,
                   help="largest denominator for fraction problems (12)")
    p.add_argument("--outdir", default=os.path.join(
                   os.path.dirname(os.path.abspath(__file__)), "output"),
                   help="where to write the .html files")
    return p.parse_args()


def finalize_args(args):
    count_d, cols_d, title_d, sub_d = DEFAULTS[args.style]
    if args.count is None:
        args.count = count_d
    if args.columns is None:
        args.columns = cols_d
    if args.title is None:
        args.title = title_d
    if args.subtitle is None:
        args.subtitle = sub_d
    # restrict ops to what the style supports
    allowed = ALLOWED_OPS[args.style]
    chosen = args.ops if args.ops else allowed
    args.ops = [o for o in chosen if o in allowed] or allowed
    return args


def main():
    args = finalize_args(parse_args())
    os.makedirs(args.outdir, exist_ok=True)
    base_seed = args.seed if args.seed is not None else random.randrange(1 << 30)
    stamp = date.today().isoformat()

    written = []
    for n in range(1, args.sets + 1):
        rng = random.Random(base_seed + n)
        if args.style == "all":
            html = render_all_document(build_all_sections(rng, args), args)
        else:
            html = render_document(build_problems(rng, args), args)
        suffix = f"-{n}" if args.sets > 1 else ""
        path = os.path.join(args.outdir,
                            f"worksheet-{args.style}-{stamp}{suffix}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        written.append(path)

    print(f"Created {len(written)} '{args.style}' worksheet(s):")
    for path in written:
        print(f"  {path}")
    print("\nOpen any file in a web browser and print (or Save as PDF).")
    print(f"Seed: {base_seed}  (reuse with --seed {base_seed} to reproduce)")


if __name__ == "__main__":
    main()
