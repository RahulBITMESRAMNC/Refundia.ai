import sys
from deepeval.evaluate.configs import AsyncConfig
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv


load_dotenv()

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]/"agent")
)

from agent import agent
from dataset import dataset
from model import eval_model

from deepeval.metrics import PlanQualityMetric
from deepeval.integrations.langchain import CallbackHandler


metrics=[PlanQualityMetric(threshold=0.8,model=eval_model,include_reason=True)]

# replace the final loop with this
for golden in dataset.evals_iterator(
    metrics=metrics,
    async_config=AsyncConfig(run_async=False),
):
    agent.invoke(
        {"messages": [{"role": "user", "content": golden.input}]},
        config={
            "configurable": {"thread_id": str(uuid4())},
            "callbacks": [CallbackHandler()],
        },
    )

