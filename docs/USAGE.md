Usage
=====

Quick examples showing how to import and use the public API in `modelito`.

Basic imports
-------------

```py
from modelito import (
    __version__,
    count_tokens,
    OllamaConnector,
    OllamaProvider,
)

print("modelito", __version__)

# token counting
print(count_tokens("Hello world"))

# create a connector (does not start any external process)
conn = OllamaConnector(host="localhost", port=11434)

# create a provider instance (compatibility shim)
provider = OllamaProvider(connector=conn)
```

Installation
-------------

- Install for development: `pip install -e .`
- Build artifacts: `python -m build` (requires `build` package)
- Install from wheel: `pip install dist/modelito-<version>-py3-none-any.whl`

Try the example
---------------

There is a small example script demonstrating the public API at:

[examples/quickstart.py](examples/quickstart.py)

Run it with:

```sh
python examples/quickstart.py
```
