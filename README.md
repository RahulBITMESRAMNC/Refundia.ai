# Refundia

**Your refund bot, cross-examined.**

Most agent demos end the moment a happy path works. One screenshot, one green checkmark, and everyone moves on. Refundia is what happens when you refuse to stop there.

It's an evaluation rig built around a small customer-support agent that processes refund requests for a fictional stationery shop. The agent looks up purchases, checks how old they are, works out what's owed, and issues a refund ticket — or, just as often, explains why it won't. The rig's job is to find out whether it actually gets all of that right, and whether it knows when to say no.

The agent is the defendant. A judge model is the auditor. Seven metrics are the charges. Every test case is a trial.

---

## Table of contents

- [What the agent is supposed to know](#what-the-agent-is-supposed-to-know)
- [How the judging works](#how-the-judging-works)
- [Quickstart](#quickstart)
- [The dataset](#the-dataset)
- [The Groq rate-limit dance](#the-groq-rate-limit-dance)
- [Project layout](#project-layout)
- [Honest rough edges](#honest-rough-edges)

---

## What the agent is supposed to know

The shop has a refund policy. The agent lives or dies by it:

- **Nothing older than 30 days.** Purchase date is compared against today.
- **No time travellers.** A purchase date in the future is automatically invalid.
- **Only what they actually bought.** No refunds for items that aren't in the user's history.
- **Only what they asked for.** If they bought three things and want one back, refund one.
- **No guessing the customer.** If you don't know who you're talking to, ask. Don't fetch history for a stranger.

The agent speaks through a single structured response — an `answer` (what the user sees) and a `conversation` flag (should the loop keep going, or are we done?). That flag exists because the same agent is meant to handle multi-turn conversations, not just one-shot requests.

Behind the scenes there are four tools doing the actual work:

| Tool | What it does |
|---|---|
| `get_user_purchase_history` | Returns the purchase dict for a username, or a not-found marker. |
| `get_today_date` | Returns today's date, so the agent can age-check a purchase. |
| `calculate_right_refund` | Sums the price of the requested items the user actually owns. |
| `issue_refund_ticket` | Pretends to file a ticket — returns a confirmation string. |

Nothing fancy. The ticket is a string, not a real support queue.

---

## How the judging works

[DeepEval](https://github.com/confident-ai/deepeval) runs the whole thing. Each test case gets scored across seven metrics, and each metric has an opinion:

| Metric | The question it asks |
|---|---|
| **Answer Correctness** | Did the final message reach the same logical conclusion as the expected output? |
| **Argument Correctness** | Were the tool arguments sane? |
| **Tool Correctness** | Were the right tools called, with the right parameters? |
| **Task Completion** | Did the agent actually finish the job? |
| **Step Efficiency** | Did it get there without wandering? |
| **Plan Quality** | Was the plan it formed a good one? |
| **Plan Adherence** | Did it stick to its own plan? |

The judge is Groq running `openai/gpt-oss-120b`, wrapped in a custom `GroqJudge` class (see `model.py`). Nothing exotic — it's a thin `DeepEvalBaseLLM` subclass with retry logic, a per-loop lock, and a pacing delay. More on why below.

---

## Quickstart

You'll need **Python 3.11+** and a **Groq API key**. `uv` is assumed but `pip` works too.

```bash
git clone <your-repo>
cd refundia
uv sync

cp .env.example .env
# then fill in:
#   GROQ_API_KEY=...
#   AGENT_MODEL=llama-3.3-70b-versatile   # or whatever Groq model you want
#   JUDGE_MODEL=openai/gpt-oss-120b       # optional, this is the default
```

Run the full evaluation suite (all seven metrics, all six golden cases):

```bash
python eval_all.py
```

Or pick a fight with a single metric:

```bash
python answer_correctness.py
python argument_correctness.py
python tool_correctness.py
python task_completion.py
python step_efficiency.py
python plan_quality.py
python plan_adherence..py
```

Want to poke the agent manually? Uncomment the last line of `agent.py` and run it. It'll start a conversation loop, print each reply, and ask you to type back if the agent has a follow-up question.

---

## The dataset

Six goldens, hand-picked to cover the interesting corners:

| # | Input | What it's really testing |
|---|---|---|
| 0 | User123 asks for a book **and** a pen | Multiple eligible items, one ticket |
| 1 | User123 asks for a book | Clean single-item refund |
| 2 | **User999** asks for a book | Unknown username — the agent should ask, not guess |
| 3 | User126 asks for a water bottle | Older than 30 days — deny, explain |
| 4 | User126 asks for a backpack and a water bottle | Mixed eligibility — refund one, deny the other |
| 5 | User126 asks for sneakers | Item never purchased — deny |

The expected tool calls for each case are spelled out in `dataset.py`, so Tool Correctness has something concrete to compare against.

If you want to add your own cases, drop them into the `goldens` list. If they reference a new user, add them to `data.py` too.

---

## The Groq rate-limit dance

Groq's free tier is generous but not forgiving. It caps at around **8k tokens per minute**, and the judge prompts — DeepEval generates big ones — eat that budget fast. Two things handle it:

1. **Pacing.** `PACING_S = 12` seconds of rest between successful judge calls, `RETRY_WAIT_S = 30` after any 429. This is slow, and that's the point.
2. **A per-event-loop lock.** Async calls to the judge serialise through `_get_lock()`, so parallel evaluation doesn't stampede the rate limit.

Two other small things worth knowing:

- The judge writes the full prompt it sends to `judge_prompt_debug.txt` on every call. It gets overwritten each time, but if a score comes back weird, open it and see what the judge was actually told.
- `CacheConfig(use_cache=False)` in `eval_all.py` is deliberate. DeepEval will otherwise cache answers and skip the LLM call entirely — great for your wallet, terrible for your trust in the numbers.

---

## Project layout

```
refundia/
├── agent.py                  # LangChain agent + conversation loop
├── tools.py                  # the four refund tools
├── prompts.py                # system prompt — the agent's rulebook
├── objects.py                # reply / PurchaseItem schemas
├── data.py                   # the fake store: users and their purchases
├── models.py                 # agent model (Groq, from .env)
├── model.py                  # GroqJudge — the evaluator, with retries
├── dataset.py                # six golden test cases
├── eval_all.py               # run every metric at once
├── answer_correctness.py     # one script per metric, for when you
├── argument_correctness.py   #   want to be picky about what you fix
├── tool_correctness.py
├── task_completion.py
├── step_efficiency.py
├── plan_quality.py
├── plan_adherence..py
└── judge_prompt_debug.txt    # last prompt the judge saw
```

`uv.lock` pins everything. `pyvenv.cfg` tells you the Python that built it.

---

## Honest rough edges

Every project has these. Better to name them than pretend otherwise.

- **Single-turn evaluation only.** The agent's `reply` schema supports multi-turn, but every script in the harness calls `agent.invoke` exactly once. Conversations aren't tested yet.
- **No real auth.** Anybody can claim to be User123. The tools trust the username they're given. Fine for a mock store, not fine for production.
- **The 30-day rule lives in the prompt.** None of the tools enforce it — the LLM has to compute it from dates on its own. That's an interesting test of the model, but it means a smarter model and a stricter tool would give you different failure modes.
- **`issue_refund_ticket` doesn't issue anything.** It returns a string. That's the whole refund pipeline.
- **One typo to fix.** The file `plan_adherence..py` has a double dot. Rename it and update `eval_all.py` if it's ever imported.

If you fix any of these, the harness is right there, waiting to tell you whether you actually did.

---

## Closing

Refundia exists because "it works on my machine" isn't a claim you can verify about an LLM. You can verify that it passes six cases against seven metrics on a Tuesday. That's not the same as shipping, but it's a start.

If you extend it — more goldens, multi-turn cases, real tool validation — the harness will grade you on it too. That's the deal.

---

*Refundia is a working name. Rename the repo, the `name` field in `pyproject.toml`, and the tagline whenever you find one you like better.*