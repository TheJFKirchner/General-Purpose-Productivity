# jsonschema

**Used for:** checking structured replies against the caller's JSON Schema (`Agent(output_schema=...)`,
`ask_structured()`), engine-neutrally, in `agentlib/structured.py`. Also checks the schema itself when an
`Agent` is built (`check_schema`).

**Why a direct dependency:** it was already installed (the `mcp` package that `claude-agent-sdk` pulls in
requires it), but agentlib now imports it itself, so `pyproject.toml` lists `jsonschema>=4`.

**API used:**
- `jsonschema.validators.validator_for(schema)` picks the validator class from the schema's `$schema`
  (Draft 2020-12 when absent); `.check_schema(schema)` raises `jsonschema.SchemaError` for a bad schema.
- `Validator(schema).iter_errors(data)` yields every `ValidationError`; `.message` is human-readable and
  `.absolute_path` is the path into the data. We sort by path and report the first, plus a count.

**Links:**
- https://python-jsonschema.readthedocs.io/en/stable/validate/
- https://python-jsonschema.readthedocs.io/en/stable/api/jsonschema/validators/

**Gotchas:**
- `jsonschema.__version__` is deprecated (warns); use `importlib.metadata.version("jsonschema")` if needed.
- Unknown `type` values are only caught by `check_schema`, not by validating data, so always check the schema.
- Claude's native structured output (`output_format` json_schema -> CLI `--json-schema`) already validates on
  the CLI side; we validate again so every engine (and the fake) behaves the same.
