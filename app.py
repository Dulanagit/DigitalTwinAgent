from dotenv import load_dotenv
import os
from openai import OpenAI
import gradio as gr
import json

from context import SYSTEM_PROMPT, EVALUATOR_SYSTEM_PROMPT
from tools import TWIN_TOOLS,EVALUATOR_TOOLS, EVALUATOR_TOOL_CHOICE, handle_tool_calls



load_dotenv(override=True)
groq_api = os.getenv("GROQ_API_KEY")
openai = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_api)

GROQ_MODEL="openai/gpt-oss-20b"

def evaluate(agent_response):
    messages = [{"role": "system", "content": EVALUATOR_SYSTEM_PROMPT}] + [{"role": "user", "content": agent_response}]
    response = openai.chat.completions.create(model=GROQ_MODEL, messages=messages, tools=EVALUATOR_TOOLS, tool_choice=EVALUATOR_TOOL_CHOICE)

    if response.choices[0].finish_reason=="tool_calls":
        try:
            tool_call = response.choices[0].message.tool_calls[0]
            is_pass = json.loads(tool_call.function.arguments).get("is_pass")
            evaluator_response = json.loads(tool_call.function.arguments).get("feedback_message")
        except json.JSONDecodeError:
              return False, "System Error: Evaluator produced invalid JSON. Please try again."
    else:
        is_pass = False
        evaluator_response = "System Error: The evaluator failed to output a structured decision. Please slightly rephrase your response and try again."

    return is_pass, evaluator_response

def chat(message, histroy):
    evaluation_passed = False
    max_tries = 3
    attempt = 0
    histroy = [{"role":h["role"], "content":h["content"]} for h in histroy]
    messages = [{"role":"system", "content":SYSTEM_PROMPT}] + histroy + [{"role":"user", "content":message}]
    response = openai.chat.completions.create(model=GROQ_MODEL, messages=messages, tools=TWIN_TOOLS)

    while response.choices[0].finish_reason=="tool_calls":
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        results = handle_tool_calls(tool_calls)
        messages.append(response_message)
        messages.extend(results)
        response = openai.chat.completions.create(model=GROQ_MODEL, messages=messages, tools=TWIN_TOOLS)

    while not evaluation_passed and attempt<max_tries:
        agent_response = response.choices[0].message.content
        if not agent_response:
                    break
        
        is_pass, evaluator_message = evaluate(agent_response)

        if is_pass:
                evaluation_passed = True
        else:
                attempt += 1
                messages.append(response.choices[0].message)
                messages.append({"role": "user", "content": f"Evaluator's Response: {evaluator_message}"})
                response = openai.chat.completions.create(model=GROQ_MODEL, messages=messages, tools=TWIN_TOOLS)
        
    return response.choices[0].message.content


gr.ChatInterface(chat).launch(inbrowser=True)