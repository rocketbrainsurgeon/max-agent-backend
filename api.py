from fastapi import FastAPI
from swarm import Swarm
from agents import based_agent
from fastapi.concurrency import run_in_threadpool

app = FastAPI()
client = Swarm()

messages = []


@app.get("/")
def read_root():
    return {"message": "API is working"}


@app.get("/wallet")
def wallet_info(address: str):
    return {"data": address}


@app.get("/chat")
async def process_data(message: str):
    print("Message received:", message)
    messages.append({"role": "user", "content": message})

    response = await run_in_threadpool(
        client.run,  # Pass the blocking function
        agent=based_agent,
        messages=messages,
        context_variables={},
        stream=False,
        debug=False,
    )
    # print(response)
    messages.extend(response.messages)
    return {"result": "Processed", "response": response.messages}
