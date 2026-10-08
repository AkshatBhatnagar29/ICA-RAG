# Generation

`LLMProvider` is a small protocol: `generate(system_prompt, user_prompt) ->
str`. `GroqProvider` implements it with `httpx.AsyncClient` against Groq's
OpenAI-compatible chat-completions endpoint, model `openai/gpt-oss-20b`,
temperature zero, JSON response format, bounded timeout/retries, and configured
output tokens.

Timeouts/network errors and 5xx responses are retried with bounded jittered
backoff. 429, authentication, malformed request/response, and missing key errors
are normalized into typed `LLMError` subclasses. Metrics record outcomes and
latency; prompts and secrets are not logged.

`prompts.py` establishes the document-as-data boundary and asks for a strict
JSON answer/citation shape. `output.py` validates the untrusted response with
Pydantic. The application owns citation metadata; the model cannot overwrite
page/document fields. Provider output never writes canonical database state.

At the normal path, no authorized evidence means no provider call. At the agent
path, tool failures, insufficient evidence, malformed JSON, and citation failure
become explicit safe states. The LLM is a synthesizer over bounded evidence, not
an authorization engine or legal decision-maker.
