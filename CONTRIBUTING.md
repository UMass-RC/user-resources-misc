## install:

```shell
python3.12 -m venv ./venv
source ./venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt
```

or...

```shell
uv venv --python=3.12 ./venv
uv pip install --python=./venv/bin/python -e .
uv pip install --python=./venv/bin/python -r requirements-dev.txt
```

## test:

```shell
PYTHONPATH="$PWD" pytest -s test
```

or...

```shell
(builtin cd test && PYTHONPATH="$(dirname "$PWD")" python -m unittest test*)
```
