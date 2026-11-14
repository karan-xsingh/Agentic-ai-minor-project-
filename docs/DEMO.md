# Demo script (about 6 minutes)

Before you start: server running (`uvicorn app.main:app`), browser open at http://127.0.0.1:8000,
dark mode off (projectors wash out dark themes), browser zoom at 110%.

## 1. The idea (30 seconds)
"Most AI tools that answer questions about data can make numbers up. This one cannot hide that.
The AI only decides which analysis to run. Python does all the arithmetic. Then a separate checker
compares every number in the answer with the calculation that produced it."

## 2. Load data (30 seconds)
Click **Try the sample sales data**. Point at the overview: 500 rows, 5 columns, no missing values,
and the revenue chart with one very large order on the right edge.

## 3. A simple question (1 minute)
Ask: **Which region has the highest total revenue?**
- Expected: North, 45,637,708. Badge says Verified.
- Click the green number. The page jumps to the exact calculation (`group_aggregate`) that produced it.
- Open **How the agent worked**: planned, calculated, wrote the answer, checked the numbers.

## 4. A question that needs a special tool (1 minute)
Ask: **How much higher is North revenue than South revenue, in percent?**
- Expected: about 30.81%.
- Say: "The AI does not compute the percentage. It calls a `compare_groups` tool."

## 5. Time and honesty about incomplete data (1 minute)
Ask: **Show the quarterly revenue trend.**
- Expected: 2025Q1 26,723,001 down to 2026Q1 20,574,193, about -23.0%.
- Say: "The data ends in mid May 2026, so 2026Q2 is incomplete. The tool leaves it out of the comparison
  instead of reporting a fake collapse."

## 6. Saying no (1 minute)
Ask: **What is the profit margin of each product?**
- Expected: it says the data has no profit information. It does not invent a number.

## 7. Evidence it works (1 minute)
Show `backend/evaluation/results/latest.md`: the question set, accuracy, share of numbers verified,
response time. Tell the story: the first run found a real bug (summary questions failed); it was fixed
and measured again.

## Backup plan
If the internet or the LLM is down: the Welcome screen, overview, and history of earlier answers still
work. Open an earlier question under "Earlier questions" and walk through it.

## Questions you may be asked
**Can the AI still be wrong?** Yes. The checker proves each number came from a calculation. It cannot prove
the AI chose the right calculation. That is why we measure tool choice separately in the evaluation.

**Why not let the AI write Python code?** Safety and checkability. Fixed, tested tools cannot delete files
or run arbitrary commands, and every result can be traced.

**What happens if the AI makes up a number?** The checker finds no matching calculation, the report is
rewritten once, and anything still unmatched is marked in red with a "Needs review" badge.

**What are the limits?** One table at a time, a fixed set of eight tools, quality depends on the LLM,
no user accounts, SQLite instead of a server database.

**What would you add next?** More tools (joins, forecasting), multi-sheet files, PostgreSQL and logins.
