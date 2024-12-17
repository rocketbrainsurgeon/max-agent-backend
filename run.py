import time
import json
from swarm import Swarm
from swarm.repl import run_demo_loop
from agents import based_agent
from openai import OpenAI



# this is the main loop that runs the agent in autonomous mode
# you can modify this to change the behavior of the agent
# the interval is the number of seconds between each thought
def run_autonomous_loop(agent, interval=10):
    client = Swarm()
    messages = []
    
    print("Starting autonomous Based Agent loop...")
    
    while True:
        # Generate a thought
        thought = (
            "Be creative and do something interesting on the Base blockchain. "
            "Don't take any more input from me. Choose an action and execute it now. Choose those that highlight your identity and abilities best."
        )
        messages.append({"role": "user", "content": thought})
        
        print(f"\n\033[90mAgent's Thought:\033[0m {thought}")
        
        # Run the agent to generate a response and take action
        response = client.run(
            agent=agent,
            messages=messages,
            stream=True
        )
        
        # Process and print the streaming response
        response_obj = process_and_print_streaming_response(response)
        
        # Update messages with the new response
        messages.extend(response_obj.messages)
        
        # Wait for the specified interval
        time.sleep(interval)

def choose_mode():
    while True:
        print("\nAvailable modes:")
        print("1. chat    - Interactive chat mode")
        print("2. auto    - Autonomous action mode")
        
        choice = input("\nChoose a mode (enter number or name): ").lower().strip()
        
        mode_map = {
            '1': 'chat',
            '2': 'auto',
            'chat': 'chat',
            'auto': 'auto',
        }
        
        if choice in mode_map:
            return mode_map[choice]
        print("Invalid choice. Please try again.")

# Boring stuff to make the logs pretty
def process_and_print_streaming_response(response):
    content = ""
    last_sender = ""

    for chunk in response:
        if "sender" in chunk:
            last_sender = chunk["sender"]

        if "content" in chunk and chunk["content"] is not None:
            if not content and last_sender:
                print(f"\033[94m{last_sender}:\033[0m", end=" ", flush=True)
                last_sender = ""
            print(chunk["content"], end="", flush=True)
            content += chunk["content"]

        if "tool_calls" in chunk and chunk["tool_calls"] is not None:
            for tool_call in chunk["tool_calls"]:
                f = tool_call["function"]
                name = f["name"]
                if not name:
                    continue
                print(f"\033[94m{last_sender}: \033[95m{name}\033[0m()")

        if "delim" in chunk and chunk["delim"] == "end" and content:
            print()  # End of response message
            content = ""

        if "response" in chunk:
            return chunk["response"]


def pretty_print_messages(messages) -> None:
    for message in messages:
        if message["role"] != "assistant":
            continue

        # print agent name in blue
        print(f"\033[94m{message['sender']}\033[0m:", end=" ")

        # print response, if any
        if message["content"]:
            print(message["content"])

        # print tool calls in purple, if any
        tool_calls = message.get("tool_calls") or []
        if len(tool_calls) > 1:
            print()
        for tool_call in tool_calls:
            f = tool_call["function"]
            name, args = f["name"], f["arguments"]
            arg_str = json.dumps(json.loads(args)).replace(":", "=")
            print(f"\033[95m{name}\033[0m({arg_str[1:-1]})")

def main():
    mode = choose_mode()
    
    mode_functions = {
        'chat': lambda: run_demo_loop(based_agent, stream=True),
        'auto': lambda: run_autonomous_loop(based_agent)
    }
    
    print(f"\nStarting {mode} mode...")
    mode_functions[mode]()

if __name__ == "__main__":
    print("Starting Max Agent...")
    main()



