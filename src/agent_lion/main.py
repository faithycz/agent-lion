import gradio as gr
from dotenv import load_dotenv

from agent_lion.agent import create_search_agent

load_dotenv(override=True)

def chat(message, history):
    """Process user messages to generate and return a response from the search agent."""

    # create the search agent
    agent = create_search_agent(model_name="gpt-5.4-nano", model_provider="openai")

    # send the user message and conversation history to the agent and return the agent's response
    response = agent.invoke({"messages": history + [{"role": "user", "content": message}]})
    return response["messages"][-1].content

# launch the Gradio chat interface
gr.ChatInterface(chat).launch(inbrowser=True)