import gradio as gr
from dotenv import load_dotenv

from agent_lion.agent import create_search_agent

load_dotenv(override=True)

def chat(message, history):
    agent = create_search_agent(model_name="gpt-5.4-nano", model_provider="openai")

    response = agent.invoke({"messages": history + [{"role": "user", "content": message}]})
    return response["messages"][-1].content

gr.ChatInterface(chat).launch(inbrowser=True)