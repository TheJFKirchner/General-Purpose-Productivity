# MCP sign-in: OAuth, .env references and token from a command (draft, parked)

Status: draft (parked by the user; nothing approved, nothing built)
Date: 2026-11-17

A scoping conversation about more ways for an MCP server in the library (request 27) to get its credentials, so that people are not typing tokens into Launchpad: an OAuth sign-in, references to variables kept in `.env` files, and a token produced by running a command. The research was done and assumptions were shown, but the user parked it before answering the open questions, to move on to the sidebar and workflows.

## What the user asked for

- A server should be usable with either a personal access token or an OAuth sign-in.
- Most people keep tokens in a `.env` file, so the MCP connection should be able to reference a `.env` variable instead of having the value typed into Launchpad.
- The user then pointed out that someone signed in through the GitHub command-line tool is a different, easier case than registering an app.

## Assumptions shown (not confirmed, not corrected)

1. Built on top of the MCP library.
2. A URL server gets a "How to sign in" choice: none, token, or OAuth sign-in. A command server keeps its environment variables.
3. A token, or any header or environment value, can be typed in or picked as a reference to a variable. A reference shows as its name and is not masked.
4. Values behind references are read fresh each time a server is tested or given to an agent. A reference whose variable cannot be found makes the server fail its test with a message naming the variable.
5. OAuth has a Sign in button that opens the normal browser, not the Launchpad window, and a Sign out button.
6. Launchpad renews an OAuth sign-in by itself; if renewal fails the server shows "sign in again" and counts as failing.
7. Typed secrets keep working unchanged.
8. Tests use a pretend sign-in server on the local computer and spend no tokens.
9. A fourth choice, "Token from a command": the user gives a command (for example the GitHub tool's command that prints its token), Launchpad runs it each time the server is tested or given to an agent and uses the output as the token; nothing is stored; a failing or empty command fails the test with the command's error.

## Left open (asked, not answered)

1. Which `.env` files. Recommended: a short list of `.env` files in Settings, added by browsing; names looked up in those files in order, then in the computer's environment variables; the form offers the names found, never values. Rejected alternative: always the `.env` of the working folder, which breaks when the folder changes.
2. Where OAuth sign-ins are kept. Recommended: the operating system's protected store (Windows Credential Manager, macOS Keychain) through the `keyring` library, not a file in `.launchpad`.
3. Any server or GitHub only. Recommended: the general MCP standard, with optional app ID, app secret and scopes fields for servers that need a registered app.

## Research findings worth keeping

Checked against live documentation on 2026-11-17.

- **GitHub's hosted MCP server** supports OAuth for outside tools but does not let a tool register itself. A tool must bring the ID and secret of its own registered GitHub OAuth App or GitHub App (return address `http://127.0.0.1/callback`; the port may differ at run time), and an organisation may have to approve the app. So for GitHub, OAuth is more setup than a token. A personal access token as a Bearer header is documented. A token from the GitHub command-line tool is probably accepted (the documentation says any valid access token) but this was not confirmed; it would be the first live test.
- **Linear, Notion, Sentry and Atlassian** hosted servers all let a tool register itself, so a generic client needs only the address and a sign-in.
- **The MCP sign-in standard** requires discovery of the server's sign-in details, PKCE, a `resource` value on requests, and a return address on localhost or HTTPS that is matched exactly.
- **The official `mcp` Python package** has an OAuth client (`OAuthClientProvider` with a `TokenStorage` of four async methods) that does discovery, PKCE, registration and renewal. It has no "just get a token" call: run one cheap request through it, then read the token from storage. A pre-registered ID and secret are supplied by seeding the storage. Two caveats: it does not save expiry across restarts (store `expires_at` ourselves), and a 401 starts the full browser flow, so background use must raise "sign-in needed" instead.
- **Storage:** `keyring` is the usual choice. Windows caps an entry at 2,560 bytes, so store each token as its own entry and keep non-secret details (expiry, client ID) in an ordinary file.
- **Lifetimes:** hours, typically. Renew just before a test or a run; a very long run can outlast its sign-in and should show a warning, not fail silently.
- **`.env`:** `python-dotenv`'s `dotenv_values()` reads a file without touching the process environment.

## Facts about today's code that a build would rest on

- `agent_config` in `app/mcplib.py` is the one place a saved server becomes what a test or an agent run receives; `.env` values and fresh tokens would be supplied there. It is sync; its callers that would await a renewal are already async.
- `${VAR}` and `${VAR:-default}` are expanded from the computer's environment only. A missing variable is left as literal text with no warning; this should become a failed test naming the variable.
- A value that is only a reference is shown unmasked, but `Bearer ${TOKEN}` is masked although it holds no secret.
- Launchpad's port is random per launch; a sign-in return address needs a fixed port. Ordinary HTTP routes have no origin or access-code check, so a callback route must be validated by its own random `state` value.
- `python-dotenv` and `keyring` are not yet dependencies. `mcp` arrives through the agent SDK and is not pinned.

## Cautions raised

- A GitHub command-line token usually carries broad access (full repository access); a fine-grained token limited to one repository is narrower. This matters because MCP tools bypass Launchpad's permission cards (see request 27, known limits).
