from modelito import Client, Message

def main():
    client = Client(provider="openai", model="gpt-3.5-turbo")
    print("Available models:", client.list_models())
    msgs = [Message(role="user", content="Summarize: Hello from Client!")]
    print("Summary:", client.summarize(msgs))
    print("Streaming:")
    for chunk in client.stream(msgs):
        print(chunk, end="", flush=True)

if __name__ == "__main__":
    main()
