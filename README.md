# Unity User Resources - Misc

install:
```
pip install .
```

test:
```shell
pip install requirements-dev.txt
PYTHONPATH="$PWD" pytest test
```

or...

```shell
(builtin cd test && PYTHONPATH="$(dirname "$PWD")" python -m unittest test*)
```
