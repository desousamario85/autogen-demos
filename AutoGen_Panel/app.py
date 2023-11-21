import os
import random
import time

import autogen
import panel as pn
import param
from autogen_utils import (
    MathUserProxyAgent,
    RetrieveUserProxyAgent,
    get_retrieve_config,
    initialize_agents,
    thread_with_trace,
)
from custom_widgets import RowAgentWidget
from panel.chat import ChatInterface
from panel.widgets import Button, PasswordInput, Switch, TextInput

TIMEOUT = 60
Q1 = "What's autogen?"
Q2 = "Write a python function to compute the sum of numbers."
Q3 = "find papers on LLM applications from arxiv in the last week, create a markdown table of different domains."
pn.extension(design="material")


def get_description_text():
    return """
    # Microsoft AutoGen: Playground

    This is an AutoGen playground.

    #### [[AutoGen](https://github.com/microsoft/autogen)] [[Discord](https://discord.gg/pAbnFJrkgZ)] [[Paper](https://arxiv.org/abs/2308.08155)] [[SourceCode](https://github.com/thinkall/autogen-demos)]
    """


pn.pane.Markdown(get_description_text(), sizing_mode="stretch_width").servable()

txt_model = TextInput(
    name="Model Name", placeholder="Enter your model name here...", value="gpt-35-turbo", sizing_mode="stretch_width"
)
pwd_openai_key = PasswordInput(
    name="OpenAI API Key", placeholder="Enter your OpenAI API Key here...", sizing_mode="stretch_width"
)
pwd_aoai_key = PasswordInput(
    name="Azure OpenAI API Key", placeholder="Enter your Azure OpenAI API Key here...", sizing_mode="stretch_width"
)
pwd_aoai_url = PasswordInput(
    name="Azure OpenAI Base Url", placeholder="Enter your Azure OpenAI Base Url here...", sizing_mode="stretch_width"
)
pn.Row(txt_model, pwd_openai_key, pwd_aoai_key, pwd_aoai_url).servable()


def get_config():
    config_list = autogen.config_list_from_json(
        "OAI_CONFIG_LIST",
        file_location=".",
    )
    if not config_list:
        os.environ["MODEL"] = txt_model.value
        os.environ["OPENAI_API_KEY"] = pwd_openai_key.value
        os.environ["AZURE_OPENAI_API_KEY"] = pwd_aoai_key.value
        os.environ["AZURE_OPENAI_API_BASE"] = pwd_aoai_url.value

        config_list = autogen.config_list_from_models(
            model_list=[os.environ.get("MODEL", "gpt-35-turbo")],
        )
    if not config_list:
        config_list = [
            {
                "api_key": "",
                "base_url": "",
                "api_type": "azure",
                "api_version": "2023-07-01-preview",
                "model": "gpt-35-turbo",
            }
        ]

    llm_config = {
        "timeout": 60,
        "cache_seed": 42,
        "config_list": config_list,
        "temperature": 0,
    }

    return llm_config


btn_add = Button(name="+", button_type="success")
btn_remove = Button(name="-", button_type="danger")
switch_code = Switch(name="Run Code", sizing_mode="fixed", width=50, height=30, align="end")
pn.Row(
    pn.pane.Markdown("## Add or Remove Agents: "),
    btn_add,
    btn_remove,
    pn.pane.Markdown("### Run Code: "),
    switch_code,
).servable()


column_agents = pn.Column(
    RowAgentWidget(
        value=[
            "Boss",
            "The boss who ask questions and give tasks. Reply `TERMINATE` if everything is done.",
            "UserProxyAgent",
            "",
        ]
    ),
    sizing_mode="stretch_width",
)
column_agents.append(
    RowAgentWidget(
        value=[
            "Senior_Python_Engineer",
            "You are a senior python engineer. Reply `TERMINATE` if everything is done.",
            "AssistantAgent",
            "",
        ]
    ),
)
column_agents.append(
    RowAgentWidget(
        value=[
            "Product_Manager",
            "You are a product manager. Reply `TERMINATE` if everything is done.",
            "AssistantAgent",
            "",
        ]
    ),
)

column_agents.servable()


def add_agent(event):
    column_agents.append(RowAgentWidget(value=["", "", "AssistantAgent", ""]))


def remove_agent(event):
    column_agents.pop(-1)


btn_add.on_click(add_agent)
btn_remove.on_click(remove_agent)


def send_messages(recipient, messages, sender, config):
    chatiface.send(messages[-1]["content"], user=messages[-1]["name"], respond=False)
    return False, None  # required to ensure the agent communication flow continues


def init_groupchat(event, collection_name):
    llm_config = get_config()
    agents = []
    for row_agent in column_agents:
        agent_name = row_agent[0][0].value
        system_msg = row_agent[0][1].value
        agent_type = row_agent[0][2].value
        docs_path = row_agent[1].value
        retrieve_config = (
            get_retrieve_config(
                docs_path,
                txt_model.value,
                collection_name=collection_name,
            )
            if agent_type == "RetrieveUserProxyAgent"
            else None
        )
        code_execution_config = (
            (
                {
                    "work_dir": "coding",
                    "use_docker": False,  # set to True or image name like "python:3" to use docker
                },
            )
            if switch_code.value
            else False
        )
        agent = initialize_agents(
            llm_config, agent_name, system_msg, agent_type, retrieve_config, code_execution_config
        )
        agent.register_reply([autogen.Agent, None], reply_func=send_messages, config={"callback": None})
        agents.append(agent)

    groupchat = autogen.GroupChat(
        agents=agents, messages=[], max_round=12, speaker_selection_method="round_robin", allow_repeat_speaker=False
    )  # todo: auto, sometimes message has no name
    manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm_config)
    return agents, manager


def agents_chat(init_sender, manager, contents):
    if isinstance(init_sender, (RetrieveUserProxyAgent, MathUserProxyAgent)):
        init_sender.initiate_chat(manager, problem=contents)
    else:
        init_sender.initiate_chat(manager, message=contents)


def agents_chat_thread(init_sender, manager, contents):
    """Chat with the agent through terminal."""
    thread = thread_with_trace(target=agents_chat, args=(init_sender, manager, contents))
    thread.start()
    thread.join(TIMEOUT)
    try:
        thread.join()
        if thread.is_alive():
            thread.kill()
            thread.join()
            chatiface.send("Timeout Error: Please check your API keys and try again later.")
    except Exception as e:
        chatiface.send(str(e) if len(str(e)) > 0 else "Invalid Request to OpenAI, please check your API keys.")


def reply_chat(contents, user, instance):
    # print([message for message in instance.objects])
    if hasattr(instance, "collection_name"):
        collection_name = instance.collection_name
    else:
        collection_name = f"{int(time.time())}_{random.randint(0, 100000)}"
        instance.collection_name = collection_name

    column_agents_list = [agent[0][0].value for agent in column_agents]
    if not hasattr(instance, "agent_list") or instance.agents_list != column_agents_list:
        agents, manager = init_groupchat(None, collection_name)
        instance.manager = manager
        instance.agents = agents
        instance.agents_list = column_agents_list
    else:
        agents = instance.agents
        manager = instance.manager

    init_sender = None
    for agent in agents:
        if "UserProxy" in str(type(agent)):
            init_sender = agent
            break
    if not init_sender:
        init_sender = agents[0]
    agents_chat_thread(init_sender, manager, contents)
    # agents_chat(init_sender, manager, contents)


chatiface = ChatInterface(
    callback=reply_chat,
    height=600,
)

chatiface.send(
    "Enter a message in the TextInput below to start chat with AutoGen!",
    user="System",
    respond=False,
)
chatiface.servable()

btn_msg1 = Button(name=Q1, sizing_mode="stretch_width")
btn_msg2 = Button(name=Q2, sizing_mode="stretch_width")
btn_msg3 = Button(name=Q3, sizing_mode="stretch_width")
pn.Column(
    pn.pane.Markdown("## Message Examples: ", sizing_mode="stretch_width"),
    btn_msg1,
    btn_msg2,
    btn_msg3,
    sizing_mode="stretch_width",
).servable()


def load_message(event):
    if event.obj.name == Q1:
        chatiface.send(Q1)
    elif event.obj.name == Q2:
        chatiface.send(Q2)
    elif event.obj.name == Q3:
        chatiface.send(Q3)


btn_msg1.on_click(load_message)
btn_msg2.on_click(load_message)
btn_msg3.on_click(load_message)


btn_example1 = Button(name="RAG 2 agents", button_type="primary", sizing_mode="stretch_width")
btn_example2 = Button(name="Software Dev 3 agents", button_type="primary", sizing_mode="stretch_width")
btn_example3 = Button(name="Research 6 agents", button_type="primary", sizing_mode="stretch_width")
pn.Row(
    pn.pane.Markdown("## Agent Examples: ", sizing_mode="stretch_width"),
    btn_example1,
    btn_example2,
    btn_example3,
    sizing_mode="stretch_width",
).servable()


def clear_agents():
    while len(column_agents) > 0:
        column_agents.pop(-1)


def load_example(event):
    clear_agents()
    if event.obj.name == "RAG 2 agents":
        column_agents.append(
            RowAgentWidget(
                value=[
                    "Boss_Assistant",
                    "Assistant who has extra content retrieval power for solving difficult problems.",
                    "RetrieveUserProxyAgent",
                    "",
                ]
            ),
        )
        column_agents.append(
            RowAgentWidget(
                value=[
                    "Senior_Python_Engineer",
                    "You are a senior python engineer. Reply `TERMINATE` if everything is done.",
                    "RetrieveAssistantAgent",
                    "",
                ]
            ),
        )
    elif event.obj.name == "Software Dev 3 agents":
        column_agents.append(
            RowAgentWidget(
                value=[
                    "Boss",
                    "The boss who ask questions and give tasks. Reply `TERMINATE` if everything is done.",
                    "UserProxyAgent",
                    "",
                ]
            ),
        )
        column_agents.append(
            RowAgentWidget(
                value=[
                    "Senior_Python_Engineer",
                    "You are a senior python engineer. Reply `TERMINATE` if everything is done.",
                    "AssistantAgent",
                    "",
                ]
            ),
        )
        column_agents.append(
            RowAgentWidget(
                value=[
                    "Product_Manager",
                    "You are a product manager. Reply `TERMINATE` if everything is done.",
                    "AssistantAgent",
                    "",
                ]
            ),
        )
    elif event.obj.name == "Research 6 agents":
        column_agents.append(
            RowAgentWidget(
                value=[
                    "Admin",
                    "A human admin. Interact with the planner to discuss the plan. Plan execution needs to be approved by this admin.",
                    "UserProxyAgent",
                    "",
                ]
            ),
        )
        column_agents.append(
            RowAgentWidget(
                value=[
                    "Engineer",
                    """Engineer. You follow an approved plan. You write python/shell code to solve tasks. Wrap the code in a code block that specifies the script type. The user can't modify your code. So do not suggest incomplete code which requires others to modify. Don't use a code block if it's not intended to be executed by the executor.
Don't include multiple code blocks in one response. Do not ask others to copy and paste the result. Check the execution result returned by the executor.
If the result indicates there is an error, fix the error and output the code again. Suggest the full code instead of partial code or code changes. If the error can't be fixed or if the task is not solved even after the code is executed successfully, analyze the problem, revisit your assumption, collect additional info you need, and think of a different approach to try.
""",
                    "AssistantAgent",
                    "",
                ]
            ),
        )
        column_agents.append(
            RowAgentWidget(
                value=[
                    "Scientist",
                    """Scientist. You follow an approved plan. You are able to categorize papers after seeing their abstracts printed. You don't write code.""",
                    "AssistantAgent",
                    "",
                ]
            ),
        )
        column_agents.append(
            RowAgentWidget(
                value=[
                    "Planner",
                    """Planner. Suggest a plan. Revise the plan based on feedback from admin and critic, until admin approval.
The plan may involve an engineer who can write code and a scientist who doesn't write code.
Explain the plan first. Be clear which step is performed by an engineer, and which step is performed by a scientist.
""",
                    "AssistantAgent",
                    "",
                ]
            ),
        )
        column_agents.append(
            RowAgentWidget(
                value=[
                    "Critic",
                    "Critic. Double check plan, claims, code from other agents and provide feedback. Check whether the plan includes adding verifiable info such as source URL.",
                    "AssistantAgent",
                    "",
                ]
            ),
        )

        column_agents.append(
            RowAgentWidget(
                value=[
                    "Executor",
                    "Executor. Execute the code written by the engineer and report the result.",
                    "UserProxyAgent",
                    "",
                ]
            ),
        )


btn_example1.on_click(load_example)
btn_example2.on_click(load_example)
btn_example3.on_click(load_example)
