import os
import dotenv
import autogen
from modules import llm
from modules.db import SQLManager
from sqlalchemy import create_engine, sessionmaker
import gradio as gr

dotenv.load_dotenv()

# Check environment variables
assert os.environ.get("DATABASE_URL"), "DATABASE_URL not found in .env file"
assert os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY not found in .env file"
assert os.environ.get("OPENAI_BASE_URL"), "OPENAI_BASE_URL not found in .env file"

# Get environment variables
DB_URL = os.environ.get("DATABASE_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL")

# SQLAlchemy setup
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

# Constants
POSTGRES_TABLE_DEFINITIONS_CAP_REF = "TABLE_DEFINITIONS"
RESPONSE_FORMAT_CAP_REF = "RESPONSE_FORMAT"
SQL_DELIMITER = "---------"

# Define the function for Gradio
def respond(prompt):
    prompt = f"Fulfill this database query: {prompt}. "

    with SQLManager() as db:
        db.connect_with_url(DB_URL)

        table_definitions = db.get_table_definitions_for_prompt()
        prompt = llm.add_cap_ref(
            prompt,
            f"Use these {POSTGRES_TABLE_DEFINITIONS_CAP_REF} to satisfy the database query.",
            POSTGRES_TABLE_DEFINITIONS_CAP_REF,
            table_definitions,
        )

        # Your existing autogen configuration and agent setup code
        # ...

        # Create a group chat and initiate the chat.
        groupchat = autogen.GroupChat(
            agents=[user_proxy, data_engineer, sr_data_analyst, product_manager],
            messages=[],
            max_round=20,
        )
        manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=azureai_config)

        user_proxy.initiate_chat(manager, clear_history=True, message=prompt)

        # Get the chat history to return as a response
        response = manager.get_chat_history()
        return response

# Initialize Gradio components
txt_input = gr.Textbox(
    placeholder="Enter your SQL query prompt here...",
    lines=2,
    label="SQL Query Prompt"
)
chatbot_output = gr.Chatbot(label="Response")

# Launch Gradio Interface
iface = gr.Interface(
    fn=respond,
    inputs=txt_input,
    outputs=chatbot_output,
    live=True,
    title="SQL Query Assistant",
    description="Enter your SQL query prompt below and get assistance from the AI."
)
iface.launch()
