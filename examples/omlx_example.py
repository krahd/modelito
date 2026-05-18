"""Minimal oMLX provider example.

Run a local oMLX runtime exposing an OpenAI-compatible endpoint first.
"""

from modelito import Message, OMLXProvider


provider = OMLXProvider(base_url="http://127.0.0.1:11435/v1", model="omlx")

response = provider.summarize(
    [Message(role="user", content="Explain in one line what oMLX support means.")]
)
print(response)

print("Streaming:")
for chunk in provider.stream([Message(role="user", content="Count from 1 to 3.")]):
    print(chunk, end="", flush=True)
print()
