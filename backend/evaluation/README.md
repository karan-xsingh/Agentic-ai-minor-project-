# Evaluation

Measures how well the agent answers 25 questions about `data/sales.csv`.

- The correct answers are computed independently with pandas (`cases.py`), not by the agent's own tools.
- `python -m evaluation.run` runs every question through your real LLM and writes a report to
  `evaluation/results/` (a `.md` file to read and a `.json` file with every detail).
- Three of the questions cannot be answered from the data. The agent passes those by saying so.

Run it from the `backend` folder with your LLM environment variables set:

    python -m evaluation.run --delay 4

Use only the numbers from your own real run in reports and on a resume. The test suite uses a scripted
model to check the evaluation code itself, and its 100% is not a result.
