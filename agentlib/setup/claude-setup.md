# Setting up Claude for agentlib

Three steps: install, say how you sign in, run the check. You do this once per computer.

## 1. Install

1. **Python 3.11 or newer.** In a terminal, `python --version` should print 3.11 or higher.
2. **agentlib and the Claude Agent SDK.** In a terminal, go to the agentlib folder and run:

   ```
   python -m pip install -e .
   ```

   This also installs a private copy of Claude Code that agentlib uses. If the app you are setting up has its
   own install steps (for example a "virtual environment", a private Python just for that app), follow those:
   the point is that this command runs in the same Python the app uses.
3. **Claude Code, signed in** (only if you use the normal Claude login): install it from
   <https://code.claude.com/docs/en/setup>, then type `claude` in a terminal once and sign in. If your
   company installed Claude Code for you, this is probably already done.

## 2. Say how you sign in

There is **one place** for this: the file `setup/local.toml` in the agentlib folder. It belongs to you: git
ignores it, so it is never committed and pulling library updates never overwrites it.

- **If typing `claude` in a terminal just works with your Claude account, do nothing.** No file is needed.
- Otherwise copy `setup/local.example.toml` to `setup/local.toml` and set `auth` under `[claude]`:

| Your situation | In `setup/local.toml` |
|---|---|
| You sign in to Claude Code with your Claude account (the default) | nothing, or `auth = "login"` |
| Your company set up Claude Code for you in its `settings.json` (a gateway address, a key helper command, ...) | `auth = "settings-file"` |
| You were given an address and a key or token to use | `auth = "env"` and the values under `[claude.env]` |

**`settings-file`** reads your Claude Code settings file (default `~/.claude/settings.json`, on Windows
`C:\Users\<you>\.claude\settings.json`; set `settings_file = '...'` for another one) and uses only the
sign-in parts: its `env` block, and `apiKeyHelper`, `awsAuthRefresh`, `awsCredentialExport`,
`gcpAuthRefresh`, `forceLoginMethod`, `forceLoginOrgUUID`, `forceLoginGatewayUrl`. Permissions, hooks,
plugins, model choice and everything else in that file are not used.

**`env`** passes the variables under `[claude.env]` to Claude. Write `"${NAME}"` to take a value from a
variable already set on your computer, so the secret itself is not written in the file.

An app that passes its own `env=` to agentlib wins over this file for those variables.

## 3. Test it

```
python -m agentlib.check
```

It checks the install and your setup, sends one tiny message on Haiku (a fraction of a cent), and prints
either `RESULT: WORKS` (with the model and how you signed in) or what failed and what to do. It never
prints secret values. `python -m agentlib.check --status` shows the setup without sending anything.

## If it does not work

| The check says | What to do |
|---|---|
| `NOT SET UP` | Fix each `Problem:` line it lists (they name the file and the setting) |
| `Not logged in` / `Please run /login` / `Invalid API key` | Normal login: type `claude` in a terminal and sign in. Company setup: use `auth = "settings-file"` |
| `apiKeyHelper` failing | Run the helper command from your settings file by hand; it must print a key |
| timed out | Usually a wrong gateway address, a proxy, or no network. Try `claude -p hi` in a terminal |
| a model is not available | Run `python -m agentlib.check --model <a model you can use>` |

## Your company does it differently?

This guide cannot cover every company's setup. What usually still works:

- **Amazon Bedrock, Google Vertex, Microsoft Foundry, proxies, company certificates:** these are environment
  variables (for example `CLAUDE_CODE_USE_BEDROCK`, `AWS_REGION`, `HTTPS_PROXY`, `NODE_EXTRA_CA_CERTS`). Put
  them under `[claude.env]`, or in the `env` block of your Claude Code settings file and use
  `settings-file`. The full list: <https://code.claude.com/docs/en/env-vars>.
- **Settings your company manages centrally** (managed settings) are applied by Claude Code itself; you do
  not need to copy them.
- **A gateway with single sign-on** that you sign in to with `/login` inside Claude Code is stored by Claude
  Code, so `auth = "login"` uses it.

If none of that fits, the one place to adapt is `agentlib/engines/claude_setup.py`: it reads this file and
decides what is passed to Claude (`SIGN_IN_KEYS` lists the settings-file keys used). Change it there, add a
test, and tell whoever looks after agentlib, rather than changing an app.
