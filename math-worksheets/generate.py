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
#   {"kind": "frac",  "w1":0,"w2":0,"n1":3,"n2":2,"d":8,"op":"+",
#                      "ans_whole":0,"ans_num":5}
# Generators take an optional forced `op`; when None they pick one at random
# from args.ops. The forced op lets the combo sheet balance + and - evenly.

def _h_add3(rng):
    """Standard 3-digit addition with the sum kept at or below 999."""
    a = rng.randint(100, 899)
    b = rng.randint(100, 999 - a)
    return {"kind": "h", "text": f"{a} + {b} =", "answer": a + b}


def _h_sub_noborrow(rng):
    """3-digit subtraction with no borrowing ('no pass back') -- each digit of
    the top number is >= the matching digit below it."""
    h = rng.randint(1, 9)
    t = rng.randint(0, 9)
    o = rng.randint(0, 9)
    top = 100 * h + 10 * t + o
    bot = 100 * rng.randint(1, h) + 10 * rng.randint(0, t) + rng.randint(0, o)
    return {"kind": "h", "text": f"{top} - {bot} =", "answer": top - bot}


def _h_div_by_ten(rng):
    """A 3- or 4-digit multiple of 10 divided by 10 -- shows how many tens are
    in a big number, e.g. 3450 / 10 = 345."""
    quotient = rng.randint(10, 999)            # 2- or 3-digit quotient
    number = quotient * 10                      # 3- or 4-digit multiple of 10
    return {"kind": "h", "text": f"{number} {DIV} 10 =", "answer": quotient}


def gen_horizontal(rng, args, op=None):
    # mix in some 3-digit place-builder problems when enabled
    if op is None and rng.random() < getattr(args, "three_digit_prob", 0.0):
        r = rng.random()
        if r < 0.4:
            return _h_add3(rng)
        if r < 0.8:
            return _h_sub_noborrow(rng)
        return _h_div_by_ten(rng)
    op = op or rng.choice(args.ops)
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


def gen_stacked(rng, args, op=None):
    """3-digit (configurable) addition / subtraction, vertical form."""
    op = op or rng.choice(args.ops)
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


def _rand_by_digits(rng, lo, hi):
    """Pick a number in [lo, hi], choosing the digit count uniformly first so a
    wide range (e.g. 10..99999) gives an even spread of 2-, 3-, 4-, 5-digit
    numbers instead of mostly the largest size."""
    d = rng.randint(len(str(lo)), len(str(hi)))
    lo_d = max(lo, 10 ** (d - 1)) if d > 1 else lo
    hi_d = min(hi, 10 ** d - 1)
    if lo_d > hi_d:                      # range doesn't actually cover d digits
        lo_d, hi_d = lo, hi
    return rng.randint(lo_d, hi_d)


def gen_multiplication(rng, args, op=None):
    """Multi-step stacked multiplication (multi-digit x multi-digit)."""
    a = _rand_by_digits(rng, args.mult_top_min, args.mult_top_max)
    b = _rand_by_digits(rng, args.mult_bot_min, args.mult_bot_max)
    return {"kind": "stack", "a": a, "b": b, "op": MULT,
            "answer": a * b, "work": True}


def gen_fraction(rng, args, op=None):
    """Add/subtract fractions with a common denominator. Results stay proper
    (no carrying/borrowing). May include whole-number parts (mixed numbers)
    with probability args.frac_mixed_prob, e.g. 2 1/5 + 4 2/5 = 6 3/5."""
    op = op or rng.choice(args.ops)
    d = rng.randint(3, max(3, args.max_denom))
    use_whole = rng.random() < getattr(args, "frac_mixed_prob", 0.0)
    if op == "+":
        # keep the fraction sum a strictly proper fraction: 2 <= n1+n2 <= d-1
        n1 = rng.randint(1, d - 2)
        n2 = rng.randint(1, d - 1 - n1)
        ans_num = n1 + n2
        w1 = rng.randint(1, args.max_whole) if use_whole else 0
        w2 = rng.randint(1, args.max_whole) if use_whole else 0
        ans_whole = w1 + w2
    else:
        # keep the fraction difference positive: n1 > n2
        n1 = rng.randint(2, d - 1)
        n2 = rng.randint(1, n1 - 1)
        ans_num = n1 - n2
        w2 = rng.randint(1, args.max_whole) if use_whole else 0
        w1 = rng.randint(w2, args.max_whole) if use_whole else 0
        ans_whole = w1 - w2
    return {"kind": "frac", "w1": w1, "w2": w2, "n1": n1, "n2": n2, "d": d,
            "op": op, "ans_whole": ans_whole, "ans_num": ans_num}


def gen_longdiv(rng, args, op=None):
    """Long division, drawn in the bracket form. Builds the dividend from a
    known quotient so it divides evenly (no remainder, no decimals)."""
    divisor = rng.randint(args.ld_divisor_min, args.ld_divisor_max)
    # pick a quotient that keeps the dividend within the wanted digit range
    q_lo = -(-args.ld_dividend_min // divisor)        # ceil(min / divisor)
    q_hi = args.ld_dividend_max // divisor            # floor(max / divisor)
    quotient = rng.randint(q_lo, q_hi)
    return {"kind": "longdiv", "divisor": divisor,
            "dividend": divisor * quotient, "answer": quotient}


# --- place value -----------------------------------------------------------
# each tuple: (value, singular name, plural name, chart label)
PLACES = [
    (1,           "one",              "ones",              "Ones"),
    (10,          "ten",              "tens",              "Tens"),
    (100,         "hundred",          "hundreds",          "Hundreds"),
    (1_000,       "thousand",         "thousands",         "Thousands"),
    (10_000,      "ten-thousand",     "ten-thousands",     "Ten Thousands"),
    (100_000,     "hundred-thousand", "hundred-thousands", "Hundred Thousands"),
    (1_000_000,   "million",          "millions",          "Millions"),
    (10_000_000,  "ten-million",      "ten-millions",      "Ten Millions"),
    (100_000_000, "hundred-million",  "hundred-millions",  "Hundred Millions"),
]


def _fmt(n):
    return f"{n:,}"


def pv_bundle(rng, args, count=None):
    """Ten of a place makes the next place: 10 hundreds = 1,000, etc."""
    return [{"kind": "qa", "text": f"10 {t[2]} =", "answer": _fmt(t[0] * 10)}
            for t in PLACES[:8]]            # ones .. ten-millions


def pv_howmany(rng, args, count=None):
    """The inverse ladder: how many of a place make the next one up (always 10)."""
    out = []
    for i in range(1, 9):                   # bigger = tens .. hundred-millions
        smaller, bigger = PLACES[i - 1], PLACES[i]
        out.append({"kind": "qa",
                    "text": f"How many {smaller[2]} make one {bigger[1]}?",
                    "answer": "10"})
    return out


def pv_howmuch(rng, args, count=None):
    """What is n of a place worth? 7 ten-thousands = 70,000."""
    out = []
    for _ in range(count or 9):
        t = PLACES[rng.randint(2, 7)]       # hundreds .. ten-millions
        n = rng.randint(2, 9)
        out.append({"kind": "qa", "text": f"{n} {t[2]} =",
                    "answer": _fmt(n * t[0])})
    return out


def pv_build(rng, args, count=None):
    """Compose a number from its places: 4 thousands + 5 hundreds + ... = 4,5xx."""
    out = []
    for _ in range(count or 6):
        high = rng.randint(3, 5)            # thousands .. hundred-thousands
        terms, total = [], 0
        for idx in range(high, high - 4, -1):
            d = rng.randint(1, 9)
            terms.append(f"{d} {PLACES[idx][2]}")
            total += d * PLACES[idx][0]
        out.append({"kind": "qa", "text": " + ".join(terms) + " =",
                    "answer": _fmt(total)})
    return out


NUM_WORDS = ["zero", "one", "two", "three", "four",
             "five", "six", "seven", "eight", "nine"]


def _q_dissect(rng):
    """How many of a smaller place are inside n of a larger place?
    e.g. 'How many tens are in five thousands?' -> 500."""
    larger = rng.randint(2, 6)                  # hundreds .. millions
    gap = rng.randint(1, min(3, larger))
    smaller = larger - gap
    n = rng.randint(2, 9)
    ratio = PLACES[larger][0] // PLACES[smaller][0]
    return {"kind": "qa", "space": True,
            "text": (f"How many {PLACES[smaller][2]} are in "
                     f"{NUM_WORDS[n]} {PLACES[larger][2]}?"),
            "answer": _fmt(n * ratio)}


def _q_digit_in_place(rng):
    """Identify the digit in a named place, e.g. 'In 5,897, how many hundreds
    are in the hundreds place?' -> 8."""
    ndigits = rng.randint(3, 6)
    number = rng.randint(10 ** (ndigits - 1), 10 ** ndigits - 1)
    idx = rng.randint(1, ndigits - 1)           # tens and up (skip trivial ones)
    place = PLACES[idx]
    digit = (number // place[0]) % 10
    return {"kind": "qa", "space": True,
            "text": (f"In {_fmt(number)}, how many {place[2]} are in the "
                     f"{place[2]} place?"),
            "answer": str(digit)}


def _q_count_places(rng):
    """How many digits/places does a number have?"""
    ndigits = rng.randint(4, 7)
    number = rng.randint(10 ** (ndigits - 1), 10 ** ndigits - 1)
    return {"kind": "qa", "space": True,
            "text": f"How many places (digits) does {_fmt(number)} have?",
            "answer": str(ndigits)}


def _q_regroup(rng):
    """Add one unit to a number full of 9s so it regroups, and explain why.
    e.g. 'Add 1 more one to 99. Write the new number. Why did it change?'"""
    k = rng.randint(1, 3)                        # trailing nines
    lead = "" if k == 3 else str(rng.randint(1, 9))
    number = int(lead + "9" * k)
    return {"kind": "qa", "space": True, "why": True,
            "text": (f"Add 1 more one to {_fmt(number)}. Write the new number. "
                     f"Why did it change that way?"),
            "answer": _fmt(number + 1)}


def pv_dissect(rng, args, count=None):
    """Part F mix: identifying digits in places, bundling, counting places,
    and regrouping 'why' questions -- all with open space to work in."""
    items = ([_q_digit_in_place(rng) for _ in range(3)]
             + [_q_dissect(rng) for _ in range(3)]
             + [_q_count_places(rng) for _ in range(2)]
             + [_q_regroup(rng) for _ in range(2)])
    rng.shuffle(items)
    return items


def render_pv_chart(places=None):
    cols = list(reversed(places or PLACES))     # largest place .. ones
    vals = "".join(f'<td class="pv-v">{_fmt(t[0])}</td>' for t in cols)
    names = "".join(f'<td class="pv-n">{t[3]}</td>' for t in cols)
    return f'<table class="pv-chart"><tr>{vals}</tr><tr>{names}</tr></table>'


# A full place-value table: period groups across the top (Trillions ... Ones),
# rotated place labels, tall open columns to write in, and a digit row.
PV_PERIODS = [
    ("Trillions", ["Hundred Trillions", "Ten Trillions", "Trillions"]),
    ("Billions",  ["Hundred Billions", "Ten Billions", "Billions"]),
    ("Millions",  ["Hundred Millions", "Ten Millions", "Millions"]),
    ("Thousands", ["Hundred Thousands", "Ten Thousands", "Thousands"]),
    ("Ones",      ["Hundreds", "Tens", "Ones"]),
]


def render_pv_table(number=None):
    """Render the wide place value chart (like a classroom poster). If `number`
    is given, its digits are placed in the bottom row; otherwise it's blank so
    the student can write a number and work in the open columns."""
    labels = [lbl for _, group in PV_PERIODS for lbl in group]
    n_cols = len(labels)                                   # 15 places
    digits = list(str(number)) if number is not None else []
    digits = [""] * (n_cols - len(digits)) + digits        # right-align

    title = f'<tr><td class="pvt-title" colspan="{n_cols}">Place Value</td></tr>'

    periods = "".join(
        f'<td class="pvt-period pvt-grp" colspan="3">{name}</td>'
        for name, _ in PV_PERIODS)
    period_row = f"<tr>{periods}</tr>"

    label_cells, digit_cells = "", ""
    for i, lbl in enumerate(labels):
        grp = " pvt-grp" if i % 3 == 0 else ""
        label_cells += f'<td class="pvt-col{grp}"><span class="pvt-label">{lbl}</span></td>'
        digit_cells += f'<td class="pvt-digit{grp}">{digits[i] or "&nbsp;"}</td>'
    label_row = f"<tr>{label_cells}</tr>"
    digit_row = f"<tr>{digit_cells}</tr>"

    return f'<table class="pvt">{title}{period_row}{label_row}{digit_row}</table>'


STYLES = {
    "horizontal":     gen_horizontal,
    "stacked":        gen_stacked,
    "multiplication": gen_multiplication,
    "fractions":      gen_fraction,
    "longdivision":   gen_longdiv,
}

# operations each style is allowed to use (multiplication is fixed to x)
ALLOWED_OPS = {
    "horizontal":     ["+", "-", "x", "/"],
    "stacked":        ["+", "-"],
    "multiplication": ["x"],
    "fractions":      ["+", "-"],
    "longdivision":   ["/"],
    "placevalue":     ["+"],     # unused; place value questions have no op
}

# per-style defaults: (problem count, grid columns, title, subtitle)
DEFAULTS = {
    "horizontal": (100, 4, "All Operations",
                   "Calculate each sum, difference, product, or quotient."),
    "stacked": (24, 6, "Three-Digit Addition & Subtraction",
                "Add or subtract. Line up the digits and regroup as needed."),
    "multiplication": (15, 5, "Stacked Multiplication",
                       "Multiply. Show your partial products and add them up."),
    "fractions": (18, 3, "Fractions: Add & Subtract",
                  "Add or subtract. Keep the same denominator."),
    "longdivision": (12, 4, "Long Division",
                     "Divide. These all come out even -- no remainders."),
    # the "combo platter": one sheet with a labeled section of every type
    "all": (None, None, "Mixed Math Practice",
            "Solve each problem. Show your work where you need to."),
    "placevalue": (None, None, "Place Value Practice",
                   "Each place is 10 times the place to its right."),
}
ALLOWED_OPS["all"] = ["+", "-", "x", "/"]

# sections for the "all" style. Each section gets its own uniform grid.
#   balanced=True  -> split the count evenly across the style's operations
#   overrides      -> per-section argument overrides (number ranges, etc.)
ALL_SECTIONS = [
    {"heading": "Part A — Add, Subtract, Multiply &amp; Divide",
     "style": "horizontal", "count": 20, "cols": 4},
    {"heading": "Part B — Three-Digit Addition &amp; Subtraction",
     "style": "stacked", "count": 8, "cols": 4, "balanced": True},
    {"heading": "Part C — Multiplication (2-digit × 2-digit)",
     "style": "multiplication", "count": 8, "cols": 4,
     "overrides": {"mult_top_min": 12, "mult_top_max": 99,
                   "mult_bot_min": 12, "mult_bot_max": 99}},
    {"heading": "Part D — Fractions &amp; Mixed Numbers (same denominator)",
     "style": "fractions", "count": 8, "cols": 3,
     "overrides": {"frac_mixed_prob": 0.6}},
    {"heading": "Part E — Long Division (3-digit ÷ 1-digit, no remainders)",
     "style": "longdivision", "count": 8, "cols": 4},
    {"heading": "Part F — Number Places (write each number in the chart to help you)",
     "builder": pv_dissect, "count": 10, "cols": 2, "table": True},
]

# sections for the "placevalue" style. These use a `builder` (a function that
# returns a ready list of problems) instead of a per-item generator.
PV_SECTIONS = [
    {"heading": "Part 1 — Ten of a place makes the next place",
     "builder": pv_bundle, "cols": 2},
    {"heading": "Part 2 — How many make one?",
     "builder": pv_howmany, "cols": 2},
    {"heading": "Part 3 — How much is it worth?",
     "builder": pv_howmuch, "count": 9, "cols": 3},
    {"heading": "Part 4 — Build the number",
     "builder": pv_build, "count": 6, "cols": 2},
]

# styles whose pages are built from labeled sections rather than one grid
SECTIONED = {"all": ALL_SECTIONS, "placevalue": PV_SECTIONS}


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
.cell.stack.work { min-height: 160px; }   /* lots of room to work partial products */
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
.cell.frac { align-items: center; min-height: 70px; white-space: nowrap; }
.fr { display: inline-flex; flex-direction: column; align-items: center;
      margin: 0 3px; line-height: 1.05; vertical-align: middle; }
.fr .top { border-bottom: 2px solid #111; padding: 0 6px; }
.fr .bot { padding: 0 6px; }
.whole { font-size: 18px; vertical-align: middle; margin-right: 2px; }
.op, .eq { margin: 0 5px; vertical-align: middle; }
.ans-frac.blank {
    display: inline-block; width: 34px; border-bottom: 1px solid #888;
    margin-left: 6px;
}
.ans-frac .fr { color: #c0392b; }
.ans-frac .fr .top { border-color: #c0392b; }

/* long division -- divisor ) dividend with the quotient above the bar */
.cell.longdiv { min-height: 150px; }
.ld { display: inline-flex; align-items: flex-end;
      font-family: 'Courier New', Courier, monospace; font-size: 20px; }
.ld-divisor { padding: 0 4px 2px 0; }
.ld-box { display: inline-flex; flex-direction: column; }
.ld-quotient {
    min-height: 1.3em; padding: 0 8px 1px 10px; color: #c0392b;
    font-weight: bold; text-align: left;
}
.ld-dividend {
    border-top: 2px solid #111; border-left: 2px solid #111;
    border-top-left-radius: 10px 14px; padding: 2px 8px 0 10px;
    letter-spacing: 2px;
}

/* section headings on the combined "all" sheet -- kept small and unobtrusive,
   with clear space above to separate one section from the next */
.section-title {
    font-size: 11px; font-weight: bold; margin: 20px 0 3px;
    color: #444; text-transform: uppercase; letter-spacing: 0.3px;
}
.page > .section-title:first-of-type { margin-top: 6px; }

/* place value: question with a fill-in blank */
.cell.qa { align-items: flex-start; font-size: 16px; min-height: 26px; }
.qa-blank { display: inline-block; min-width: 90px; border-bottom: 1px solid #888;
            margin-left: 8px; }
.qa-ans { color: #c0392b; font-weight: bold; margin-left: 8px; }
/* an open box under the question to work in and solve */
.qa-body { display: flex; flex-direction: column; flex: 1; }
.qa-space {
    border: 1px solid #bbb; border-radius: 4px; min-height: 56px;
    margin-top: 4px; padding: 3px 6px;
}
.qa-space-tall { min-height: 84px; }   /* room to write the number and the "why" */
.qa-space .qa-ans { margin-left: 0; }

/* full place value table (period groups + rotated labels + open columns) */
.pvt {
    border-collapse: collapse; width: 100%; table-layout: fixed;
    margin: 6px 0 14px; font-family: -apple-system, system-ui, sans-serif;
}
.pvt td { border: 1px solid #111; text-align: center; }
.pvt .pvt-grp { border-left-width: 3px; }
.pvt-title { font-size: 16px; font-weight: bold; padding: 5px; }
.pvt-period { font-size: 13px; font-weight: bold; padding: 4px 2px; }
.pvt-col { height: 1.9in; vertical-align: bottom; padding: 4px 0; }
.pvt-label {
    writing-mode: vertical-rl; transform: rotate(180deg);
    white-space: nowrap; font-size: 11px; font-weight: bold;
    display: inline-block;
}
.pvt-digit { height: 0.45in; font-size: 18px; font-weight: bold; }

/* place value reference chart across the top */
.pv-chart {
    border-collapse: collapse; width: 100%; table-layout: fixed;
    margin: 4px 0 14px; font-family: -apple-system, system-ui, sans-serif;
}
.pv-chart td {
    border: 1px solid #999; text-align: center; padding: 3px 2px;
    font-size: 9px; line-height: 1.15; word-wrap: break-word;
}
.pv-chart .pv-v { font-weight: bold; }
.pv-chart .pv-n { color: #555; }

.key-tag { color: #c0392b; }
@media print { .no-print { display: none; } body { margin: 0; } }
.no-print {
    background: #f4f4f4; border: 1px solid #ccc; padding: 10px 14px;
    font-family: -apple-system, system-ui, sans-serif; font-size: 13px;
    max-width: 8.5in; margin: 12px auto;
}

/* ---- compact mode: trim everything to fit one page ---- */
.compact .compact-head {
    display: flex; justify-content: space-between; align-items: baseline;
    border-bottom: 2px solid #111; padding-bottom: 3px; margin-bottom: 4px;
}
.compact .ch-title { font-size: 16px; font-weight: bold; }
.compact .ch-fields { font-size: 12px; color: #333; }
.compact .page { padding: 0.3in 0.45in; min-height: 0; }
.compact .grid { gap: 3px 12px; }
.compact .cell { font-size: 15px; padding: 1px; }
.compact .section-title { font-size: 10px; margin: 13px 0 2px; }
.compact .page > .section-title:first-of-type { margin-top: 2px; }
.compact .cell.stack { min-height: 56px; }
.compact .cell.stack.work { min-height: 120px; }   /* freehand working space */
.compact .stack-nums, .compact .ans-slot { font-size: 16px; }
.compact .cell.frac { min-height: 42px; }
.compact .cell.longdiv { min-height: 120px; }
.compact .ld { font-size: 17px; }
.compact .pvt-col { height: 1.5in; }
.compact .pvt-title { font-size: 14px; padding: 3px; }
.compact .pvt-period { font-size: 11px; }
.compact .pvt-label { font-size: 9.5px; }
"""


def render_horizontal(p, show):
    ans = f' <span style="color:#c0392b;font-weight:bold">{p["answer"]}</span>' if show else ""
    return f'<span class="prob">{p["text"]}</span>{ans}'


def render_stack(p, show, field=None):
    a, b, op, ans = p["a"], p["b"], p["op"], p["answer"]
    # `field` is shared across a whole section so every problem aligns the same;
    # fall back to the problem's own width when rendered on its own.
    if field is None:
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


def _stack_field(problems):
    """The widest digit count among stacked problems, so a whole section can
    share one alignment width (keeps every problem lined up in its column)."""
    widths = [max(len(str(p["a"])), len(str(p["b"])), len(str(p["answer"])))
              for p in problems if p["kind"] == "stack"]
    return max(widths) if widths else None


def _fr(num, den):
    return f'<span class="fr"><span class="top">{num}</span><span class="bot">{den}</span></span>'


def _mixed(whole, num, den):
    """Render a (possibly) mixed number: a whole part, a fraction, or both."""
    w = f'<span class="whole">{whole}</span>' if whole else ""
    return f'{w}{_fr(num, den)}'


def _mixed_answer(whole, num, den):
    """Like _mixed, but drop a zero fraction so the answer reads cleanly
    (e.g. "5" instead of "5 0/8")."""
    if whole and not num:
        return f'<span class="whole">{whole}</span>'
    return _mixed(whole, num, den)


def render_frac(p, show):
    op_sym = "+" if p["op"] == "+" else "−"  # − minus sign
    left = _mixed(p["w1"], p["n1"], p["d"])
    right = _mixed(p["w2"], p["n2"], p["d"])
    if show:
        ans = _mixed_answer(p["ans_whole"], p["ans_num"], p["d"])
        answer = f'<span class="ans-frac">{ans}</span>'
    else:
        answer = '<span class="ans-frac blank"></span>'
    return (f'{left}<span class="op">{op_sym}</span>{right}'
            f'<span class="eq">=</span>{answer}')


def render_longdiv(p, show):
    """Long division in bracket form: divisor ) dividend, with the quotient
    sitting above the bar (shown only on the answer key)."""
    quotient = str(p["answer"]) if show else "&nbsp;"
    return (
        '<span class="ld">'
        f'<span class="ld-divisor">{p["divisor"]}</span>'
        '<span class="ld-box">'
        f'<span class="ld-quotient">{quotient}</span>'
        f'<span class="ld-dividend">{p["dividend"]}</span>'
        '</span></span>'
    )


def render_qa(p, show):
    """A place value question. With "space" it gets an open box to work in and
    solve; otherwise a short inline fill-in blank. Answer shown on the key."""
    if p.get("space"):
        inner = f'<span class="qa-ans">{p["answer"]}</span>' if show else ""
        box = "qa-space qa-space-tall" if p.get("why") else "qa-space"
        return (f'<div class="qa-body"><div class="qa-text">{p["text"]}</div>'
                f'<div class="{box}">{inner}</div></div>')
    ans = (f'<span class="qa-ans">{p["answer"]}</span>' if show
           else '<span class="qa-blank"></span>')
    return f'<span class="qa-text">{p["text"]}</span>{ans}'


RENDERERS = {"h": render_horizontal, "stack": render_stack,
             "frac": render_frac, "longdiv": render_longdiv, "qa": render_qa}


def render_cell(p, index, show, field=None):
    if p["kind"] == "stack":
        body = render_stack(p, show, field)
    else:
        body = RENDERERS[p["kind"]](p, show)
    cls = p["kind"]
    if p["kind"] == "stack" and p.get("work"):
        cls += " work"
    return f'<div class="cell {cls}"><span class="qnum">{index}.</span>{body}</div>'


def render_header(args, label, subtitle):
    """The block above the problems. Compact mode collapses the bordered title,
    subtitle and name/date row into a single slim strip to save vertical space."""
    if getattr(args, "compact", False):
        return (
            '<div class="compact-head">'
            f'<span class="ch-title">{args.title}{label}</span>'
            '<span class="ch-fields">Name: _______________&nbsp;&nbsp;'
            'Date: __________</span>'
            '</div>'
        )
    return (
        f'<div class="title-box">{args.title}{label}</div>'
        f'<div class="subtitle">{subtitle}</div>'
        '<div class="meta">'
        '<span>Name: ______________________</span>'
        '<span>Date: ______________</span>'
        '</div>'
    )


def render_page(problems, args, label, show):
    rows = -(-args.count // args.columns)  # ceil -> rows per column
    field = _stack_field(problems)
    cells = "".join(render_cell(p, i, show, field)
                    for i, p in enumerate(problems, 1))
    grid_style = (f"grid-template-columns: repeat({args.columns}, 1fr);"
                  f"grid-template-rows: repeat({rows}, auto);")
    header = render_header(args, label, args.subtitle if not show else "Answer Key")
    return f"""
    <div class="page">
        {header}
        <div class="grid" style="{grid_style}">{cells}</div>
    </div>
    """


def wrap_html(title, pages, compact=False):
    body_class = "compact" if compact else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{PAGE_CSS}</style></head>
<body class="{body_class}">{''.join(pages)}</body></html>
"""


def render_document(problems, args):
    pages = [render_page(problems, args, "", False)]
    if not args.no_key:
        pages.append(render_page(
            problems, args, ' <span class="key-tag">(KEY)</span>', True))
    return wrap_html(args.title, pages, getattr(args, "compact", False))


# --- sheets built from labeled sections (the "all" and "placevalue" styles) --

def _balanced_ops(rng, ops, count):
    """A length-`count` list of ops, split as evenly as possible, shuffled."""
    seq = [ops[i % len(ops)] for i in range(count)]
    rng.shuffle(seq)
    return seq


def build_sections(rng, args, specs):
    """Return [(heading, [problems], columns), ...] from a section spec list.

    A spec either supplies a `builder` (a function returning a list of problems)
    or a `style` + `count` to generate from, optionally `balanced`."""
    sections = []
    for spec in specs:
        sec = copy.copy(args)
        for key, val in spec.get("overrides", {}).items():
            setattr(sec, key, val)
        if "builder" in spec:
            problems = spec["builder"](rng, sec, spec.get("count"))
        else:
            sec.style = spec["style"]
            sec.ops = ALLOWED_OPS[spec["style"]]
            gen = STYLES[spec["style"]]
            count = spec["count"]
            if spec.get("balanced"):
                problems = [gen(rng, sec, op)
                            for op in _balanced_ops(rng, sec.ops, count)]
            else:
                problems = [gen(rng, sec) for _ in range(count)]
        if spec.get("table"):
            extra = ("table", None)
        elif spec.get("chart"):
            extra = ("chart", PLACES[:spec["chart"]])
        else:
            extra = None
        sections.append((spec["heading"], problems, spec["cols"], extra))
    return sections


def render_section(heading, problems, columns, show, extra=None):
    rows = -(-len(problems) // columns)
    field = _stack_field(problems)
    cells = "".join(render_cell(p, i, show, field)
                    for i, p in enumerate(problems, 1))
    grid_style = (f"grid-template-columns: repeat({columns}, 1fr);"
                  f"grid-template-rows: repeat({rows}, auto);")
    header = ""
    if extra and extra[0] == "table":
        header = render_pv_table()
    elif extra and extra[0] == "chart":
        header = render_pv_chart(extra[1])
    return (f'<div class="section-title">{heading}</div>{header}'
            f'<div class="grid" style="{grid_style}">{cells}</div>')


def render_all_page(sections, args, label, show):
    body = "".join(render_section(h, p, c, show, ex)
                   for h, p, c, ex in sections)
    header = render_header(args, label, args.subtitle if not show else "Answer Key")
    chart = render_pv_chart() if args.style == "placevalue" else ""
    return f"""
    <div class="page">
        {header}
        {chart}
        {body}
    </div>
    """


def render_all_document(sections, args):
    pages = [render_all_page(sections, args, "", False)]
    if not args.no_key:
        pages.append(render_all_page(
            sections, args, ' <span class="key-tag">(KEY)</span>', True))
    return wrap_html(args.title, pages, getattr(args, "compact", False))


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Generate printable math worksheets in several styles.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--style", choices=list(STYLES) + ["all", "placevalue"],
                   default="horizontal",
                   help="worksheet style; 'all' is a combined sheet with a "
                        "section of every type and 'placevalue' drills place "
                        "value (default: horizontal)")
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
    p.add_argument("--compact", action="store_true",
                   help="slim header and tighter spacing to fit more on one page")
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
    p.add_argument("--three-digit", action="store_true",
                   help="mix in 3-digit problems: standard addition (sum <= 999) "
                        "and no-borrow subtraction, to reinforce place value")
    p.add_argument("--three-digit-prob", type=float, default=0.35,
                   help="fraction of horizontal problems that are 3-digit when "
                        "--three-digit is on (default 0.35)")
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
    p.add_argument("--mixed-numbers", action="store_true",
                   help="mix in mixed numbers (whole + fraction), e.g. 2 1/5")
    p.add_argument("--max-whole", type=int, default=5,
                   help="largest whole-number part for mixed numbers (5)")
    # long division ranges (results always divide evenly, no remainders)
    p.add_argument("--ld-divisor-min", type=int, default=2,
                   help="smallest divisor for long division (2)")
    p.add_argument("--ld-divisor-max", type=int, default=9,
                   help="largest divisor for long division (9)")
    p.add_argument("--ld-dividend-min", type=int, default=100,
                   help="smallest dividend for long division (100)")
    p.add_argument("--ld-dividend-max", type=int, default=999,
                   help="largest dividend for long division (999)")
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
    # probability a fraction problem is a mixed number (combo overrides this)
    args.frac_mixed_prob = 0.6 if args.mixed_numbers else 0.0
    # 3-digit place-builder problems only when --three-digit is set
    if not args.three_digit:
        args.three_digit_prob = 0.0
    return args


def main():
    args = finalize_args(parse_args())
    os.makedirs(args.outdir, exist_ok=True)
    base_seed = args.seed if args.seed is not None else random.randrange(1 << 30)
    stamp = date.today().isoformat()

    written = []
    for n in range(1, args.sets + 1):
        rng = random.Random(base_seed + n)
        if args.style in SECTIONED:
            sections = build_sections(rng, args, SECTIONED[args.style])
            html = render_all_document(sections, args)
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
