from openai import OpenAI
import os

client = OpenAI(
    api_key="sk-d89d20d5b4c34d4cbee7ec51b98d3d7c",
    base_url="https://api.deepseek.com/v1"
)

MODEL = "deepseek-chat"
