from dotenv import load_dotenv
import os
from openai import OpenAI, APIError
# import gradio as gr
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from context import SYSTEM_PROMPT, EVALUATOR_SYSTEM_PROMPT
from tools import TWIN_TOOLS,EVALUATOR_TOOLS, EVALUATOR_TOOL_CHOICE, handle_tool_calls

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dulanagit.github.io", "http://localhost:5173"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

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

class Conversation(BaseModel):
      message: str
      history: list[dict]

class ChatResponse(BaseModel):
      reply: str


@app.post("/chat")
def chat(conversation: Conversation):
    try:
        message = conversation.message
        history = conversation.history
        evaluation_passed = False
        max_tries = 3
        attempt = 0
        history = [{"role":h["role"], "content":h["content"]} for h in history]
        messages = [{"role":"system", "content":SYSTEM_PROMPT}] + history + [{"role":"user", "content":message}]
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

        text = response.choices[0].message.content or ""
    except APIError as exc:
        print(f"APIError: {exc}")
        raise HTTPException(
            status_code=500,
            detail="The twin could not reach the model. Try again.",
        ) from exc
    except Exception as exc:
        print(f"Exception: {exc}")
        raise HTTPException(
            status_code=500,
            detail="The twin hit an unexpected error. Try again.",
        ) from exc
    if not text:
        raise HTTPException(
            status_code=500,
            detail="The twin returned an empty reply. Try rephrasing.",
        )
        
    return ChatResponse(reply=text)


# gr.ChatInterface(chat).launch(inbrowser=True)