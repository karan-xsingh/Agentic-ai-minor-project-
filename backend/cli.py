"""Try the agent from the terminal:
    python cli.py ..\\data\\sales.csv "Which region has the highest total revenue?"
"""
import sys
from app.agent import run_agent
from app.llm import make_llm
from app.loader import load_dataset

if len(sys.argv) < 3:
    sys.exit('Usage: python cli.py <file.csv|xlsx> "<question>"')
path, question = sys.argv[1], " ".join(sys.argv[2:])
df = load_dataset(open(path, "rb").read(), path)
state = run_agent(df, question, make_llm())
print("\n=== REPORT ===\n" + state["report"])
print("\n=== EVIDENCE TRAIL ===")
for e in state["evidence"]:
    print(f"[E:{e['id']}] {e['tool']} {e['args']} -> {'ok' if e['ok'] else 'ERROR: ' + e['error']} ({e['ms']} ms)")
v = state.get("verification")
if v:
    print(f"\n=== VERIFICATION ===\nnumbers verified: {v['passed_count']}/{v['total']} ({v['score']:.0%})   "
          f"citation coverage: {v['citation_coverage']:.0%}")
    for p in v["problems"]:
        print("  PROBLEM:", p)
print(f"\nstatus={state['status']}  attempts={state['attempts']}  report_attempts={state.get('report_attempts')}  charts={len(state['charts'])}")
