from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool

from agent_lion.rag.retrieval import fetch_context

load_dotenv(override=True)

# define the system prompt for the search agent
SYSTEM_PROMPT = (
        "You are a knowledgeable, informational assistant for the Penn State IT Knowledge Base. "
        "You are chatting with a user about IT-related questions and information for Penn State. "
        "For all questions, use the search_knowledge_base tool to find relevant information in the knowledge base before answering. "
        "Base your answers on the retrieved articles only. "
        "Do not invent information or provide answers that are not supported by the knowledge base. "
        "If you don't know the answer, say so and do not make up false information."
    )

@tool
def search_knowledge_base(question: str) -> str:
    """Search the Penn State IT Knowledge Base for relevant information to a user's question."""

    # retrieve relevant documents from the knowledge base
    docs = fetch_context(question)

    return "\n\n".join(doc.page_content for doc in docs)

def create_search_agent(model_name: str, model_provider: str):
    """Create a search agent that uses the Penn State IT Knowledge Base to answer user questions."""

    # initialize the llm with the specified model name and provider
    llm = init_chat_model(model=model_name, model_provider=model_provider, temperature=0)

    # create the search agent with the llm, search tool, and system prompt
    return create_agent(
        model=llm,
        tools=[search_knowledge_base],
        system_prompt=SYSTEM_PROMPT
    )