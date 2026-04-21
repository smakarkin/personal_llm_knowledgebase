import os
from pathlib import Path

MODEL = "deepseek-chat"
VAULT_PATH = Path(r"C:\Users\smaka\OneDrive\Документы\04_Zettelkasten\Zettelkasten")


def get_client():
    from openai import OpenAI

    return OpenAI(
        api_key="sk-d89d20d5b4c34d4cbee7ec51b98d3d7c",
        base_url="https://api.deepseek.com/v1"
    )
