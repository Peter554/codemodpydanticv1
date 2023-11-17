# codemodpydanticv1

[![CI](https://github.com/Peter554/codemodpydanticv1/actions/workflows/ci.yml/badge.svg)](https://github.com/Peter554/codemodpydanticv1/actions/workflows/ci.yml)

A small codemod tool to upgrade pydantic from V1 to V2, but still use the V1 API.
Pydantic V2 exposes the V1 API. By using the V1 API we can be sure nothing
is being broken by the package upgrade, and usage can then gradually be migrated
across to the V2 API. 

```sh
pip install codemodpydanticv1

codemodpydanticv1 <file>
```

Using [ripgrep](https://github.com/BurntSushi/ripgrep) and looping over files:

```sh
for file in $(rg pydantic -g '*.py' -l); do
    echo $file
    codemodpydanticv1 $file
done
```
