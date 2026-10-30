import requests
import os
from dotenv import load_dotenv
import json

load_dotenv(override=True)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


def send_telegram_notification(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",  # Allows basic text styling (*bold*, _italic_)
    }

    headers = {"Content-Type": "application/json"}
    try:
        requests.post(url=url, headers=headers, json=data)
    except requests.RequestException as e:
        print(f"Error: {e}")




def record_user_details(email, name="not provided", notes="not provided"):  
    send_telegram_notification(f"Recording user with \nname: {name}\nemail: {email}\nnotes: {notes}")
    return "OK"

def record_unknown_question(question, name="not provided", notes="not provided"):
    send_telegram_notification(f"The person with name: {name} asks question: {question} with notes: {notes}")
    return "OK"

record_user_details_json = { 
    "name": "record_user_details",
    "description": "records the email provided by the user along with name and notes",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description":"email provided by the user"},
            "name": {"type": "string", "description": "name of the user that is providing the email"},
            "notes": {"type": "string", "description": "Any additional info about the conversation that's worth recording to give context"}
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "records any question of which the answer is not known by the digital twin",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description":"email provided by the user"},
            "name": {"type": "string", "description": "name of the user that is asking the question"},
            "notes": {"type": "string", "description": "Any additional info about the conversation that's worth recording to give context"}
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

evaluation_pass_json = {
    "name": "evaluation_pass",
    "description": "Use this tool to state if the the response is approved or not.",
    "parameters": {
        "type": "object",
        "properties": {
            "is_pass": {"type": "boolean", "description": "true/false value as the approval or not respectively."},
            "feedback_message": {
            "type": "string", 
            "description": "If is_pass is false, provide a message to guide the digital twin. If true, say 'The response is approved'."
            },
        },
        "required": ["is_pass", "feedback_message"],
        "additionalProperties": False
    }
}


def handle_tool_calls(tool_calls):
    results = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        tool = globals().get(tool_name)
        result = tool(**arguments) if tool else "Tool not found"
        results.append({"role":"tool", "content":result, "tool_call_id":tool_call.id})
    return results


TWIN_TOOLS=[
    {"type":"function", "function": record_user_details_json},
    {"type":"function", "function": record_unknown_question_json}
]

EVALUATOR_TOOLS=[
    {"type":"function", "function": evaluation_pass_json}
] 

EVALUATOR_TOOL_CHOICE = {"type": "function", "function": {"name": "evaluation_pass"}}
