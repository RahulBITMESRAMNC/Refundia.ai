from pydantic import BaseModel, Field

class reply(BaseModel):
    answer: str = Field(
        description="The message to show the user. This includes clarifying questions "
                    "as well as the final refund outcome."
    )
    conversation: bool = Field(
        description="True if you still need a reply from the user (for example, you asked "
                    "a question). False only after you have given the final refund decision."
    )

class PurchaseItem(BaseModel):
    name: str = Field(description="Name of the item purchased")