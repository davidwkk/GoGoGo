# Gemini API — `GenerateContentConfig` Reference

> **Scope:** This reference targets `gemini-3-flash-preview`. Note that `gemini-3.1-flash-live-preview` (audio-to-audio) is also available via the **Live API** with a different API surface.

All fields passed via `types.GenerateContentConfig(...)` in the Python SDK.

## Core Generation Controls

| Field               | Type        | Description                                                                                                                                                                        |
| ------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `temperature`       | `float`     | Sampling temperature (0.0–2.0). Default: 1.0. **Gemini 3: keep at 1.0.** Lowering it can cause looping or degraded reasoning on complex tasks. Use `seed` for determinism instead. |
| `top_p`             | `float`     | Nucleus sampling threshold (0.0–1.0). Only tokens with cumulative probability up to this value are considered. Default: 0.95.                                                      |
| `top_k`             | `int`       | Limits sampling to the top K most likely tokens. Default: 64 (Gemini 3 Flash).                                                                                                     |
| `max_output_tokens` | `int`       | Maximum number of tokens in the output. Use to limit response length and control costs.                                                                                            |
| `stop_sequences`    | `list[str]` | Strings that stop generation when encountered. Output terminates at the first match.                                                                                               |

## Structured Output

| Field                  | Type   | Description                                                                   |
| ---------------------- | ------ | ----------------------------------------------------------------------------- |
| `response_mime_type`   | `str`  | Response format, e.g. `"application/json"` or `"text/plain"`.                 |
| `response_schema`      | `dict` | JSON schema for structured output (alternative to `response_json_schema`).    |
| `response_json_schema` | `dict` | JSON schema for structured output — pass `TripItinerary.model_json_schema()`. |

## Thinking / Reasoning (Gemini 3 only)

| Field             | Type             | Description                                                              |
| ----------------- | ---------------- | ------------------------------------------------------------------------ |
| `thinking_config` | `ThinkingConfig` | Controls internal reasoning via `thinking_level` and `include_thoughts`. |

### `ThinkingConfig` fields:

| Field              | Type   | Description                                                                                                                                                                                                                         |
| ------------------ | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `thinking_level`   | enum   | Reasoning depth: `MINIMAL`, `LOW`, `MEDIUM`, `HIGH`.                                                                                                                                                                                |
| `include_thoughts` | `bool` | If `True`, thought summaries appear in `response.candidates[0].content.parts` as `Part.thought`. Default: `False`. **Non-streaming:** single final thought summary. **Streaming:** rolling incremental summaries during generation. |

### `ThinkingLevel` enum values:

| Value     | Description                                                                               |
| --------- | ----------------------------------------------------------------------------------------- |
| `MINIMAL` | Minimizes latency; model may think minimally even on complex tasks. Best for casual chat. |
| `LOW`     | Minimizes latency and cost; best for simple instructions or high-throughput scenarios.    |
| `MEDIUM`  | Balanced reasoning. Default for most tasks.                                               |
| `HIGH`    | Maximizes reasoning depth; may increase latency to first token. Default for Pro models.   |

### ⚠️ Migration: Gemini 2.5 → Gemini 3

| Model      | Parameter         | Type   |
| ---------- | ----------------- | ------ |
| Gemini 2.5 | `thinking_budget` | `int`  |
| Gemini 3   | `thinking_level`  | `enum` |

`thinking_budget=0` (2.5, disable thinking) → `thinking_level=MINIMAL` (3, still processes thought signatures). They are **not identical** — Gemini 3 always produces a thought signature even at `MINIMAL`.

## Determinism & Reproducibility

| Field               | Type   | Description                                                                                                      |
| ------------------- | ------ | ---------------------------------------------------------------------------------------------------------------- |
| `seed`              | `int`  | When set, the model uses this as the random seed for deterministic output. Same seed + same input = same output. |
| `response_logprobs` | `bool` | If `True`, returns log probabilities of output tokens.                                                           |
| `logprobs`          | `int`  | Number of top log probabilities to return when `response_logprobs` is set.                                       |

## Repetition & Penalty Controls

| Field               | Type    | Description                                                                      |
| ------------------- | ------- | -------------------------------------------------------------------------------- |
| `presence_penalty`  | `float` | Discourages repetition of tokens already used. Range: -2.0 to 2.0.               |
| `frequency_penalty` | `float` | Reduces repetition based on how often a token has been used. Range: -2.0 to 2.0. |

## Candidate Controls

| Field             | Type  | Description                                                                            |
| ----------------- | ----- | -------------------------------------------------------------------------------------- |
| `candidate_count` | `int` | Number of generated candidates to return (1–8). More candidates = more diverse output. |

## Safety

| Field             | Type                  | Description                                                                                                                                                                                                                                                                                                 |
| ----------------- | --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `safety_settings` | `list[SafetySetting]` | Per-category blocking thresholds. Categories: `HARM_CATEGORY_HATE_SPEECH`, `HARM_CATEGORY_SEXUALLY_EXPLICIT`, `HARM_CATEGORY_DANGEROUS_CONTENT`, `HARM_CATEGORY_HARASSMENT`, `HARM_CATEGORY_CIVIC_INTEGRITY`. Thresholds: `BLOCK_ONLY_HIGH`, `BLOCK_LOW_AND_ABOVE`, `BLOCK_MEDIUM_AND_ABOVE`, `BLOCK_NONE`. |

## System & Tools

| Field                        | Type                             | Description                                                                                                                                                        |
| ---------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `system_instruction`         | `str \| Content`                 | System prompt injected before user input.                                                                                                                          |
| `tools`                      | `list[Tool]`                     | Available tools (e.g., `ALL_TOOLS` from agent tools).                                                                                                              |
| `tool_config`                | `ToolConfig`                     | Configure tool behavior (e.g., function calling mode).                                                                                                             |
| `cached_content`             | `str`                            | Reference to a cached system instruction to avoid resending.                                                                                                       |
| `automatic_function_calling` | `AutomaticFunctionCallingConfig` | Auto-trigger function calls without going through the tool loop.                                                                                                   |
| `store`                      | `bool`                           | Configures logging behavior for the request. If set, takes precedence over project-level logging config. (Top-level request field, not inside `GenerationConfig`.) |

## Routing

| Field                    | Type                   | Description                                                                 |
| ------------------------ | ---------------------- | --------------------------------------------------------------------------- |
| `routing_config`         | `RoutingConfig`        | Controls which model variant is selected (e.g., `dynamic_model_selection`). |
| `model_selection_config` | `ModelSelectionConfig` | Preferences for model selection when using routing.                         |

## Audio / Speech (TTS models)

| Field             | Type           | Description                         |
| ----------------- | -------------- | ----------------------------------- |
| `speech_config`   | `SpeechConfig` | Voice configuration for TTS output. |
| `audio_timestamp` | `bool`         | Enable audio timestamp in output.   |

## Advanced / Misc

| Field                           | Type               | Description                                                                                                  |
| ------------------------------- | ------------------ | ------------------------------------------------------------------------------------------------------------ |
| `response_modalities`           | `list[str]`        | Output modalities, e.g. `["text"]`, `["image"]`.                                                             |
| `media_resolution`              | `str`              | Media resolution: `low`, `medium`, `high`, `ultra_high` (image-only). PDF tokens count under IMAGE modality. |
| `image_config`                  | `ImageConfig`      | Configuration for image generation.                                                                          |
| `labels`                        | `dict[str,str]`    | Custom key-value labels attached to the request.                                                             |
| `enable_enhanced_civic_answers` | `bool`             | Enable enhanced civic information in responses.                                                              |
| `model_armor_config`            | `ModelArmorConfig` | Model armor safety configuration.                                                                            |
| `http_options`                  | `HttpOptions`      | HTTP client options (proxy, timeouts).                                                                       |
| `should_return_http_response`   | `bool`             | Return raw HTTP response instead of parsed content.                                                          |

## Usage in GoGoGo

### Casual Chat (`run_agent`)

```python
config = types.GenerateContentConfig(
    system_instruction=system_instruction,
    tools=ALL_TOOLS,
    thinking_config=types.ThinkingConfig(
        thinking_level=types.ThinkingLevel.MINIMAL,
        include_thoughts=False,
    ),
)
```

### Trip Planning (`run_agent_structured`)

```python
# Phase 1: Tool gathering
config = types.GenerateContentConfig(
    system_instruction=system_instruction,
    tools=ALL_TOOLS,
    thinking_config=types.ThinkingConfig(
        thinking_level=types.ThinkingLevel.MINIMAL,
        include_thoughts=False,
    ),
)

# Phase 2: Structured output
config = types.GenerateContentConfig(
    system_instruction=system_instruction,
    response_mime_type="application/json",
    response_json_schema=TripItinerary.model_json_schema(),
    thinking_config=types.ThinkingConfig(
        thinking_level=types.ThinkingLevel.MINIMAL,
        include_thoughts=False,
    ),
)
```

## Gemini 3-Specific Features

| Feature                           | Description                                                                                                                                        |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Thought summaries**             | With `include_thoughts=True`, `response.candidates[0].content.parts` contains `Part.thought` entries with the model's reasoning trace.             |
| **Multimodal function responses** | Function responses can now include images/PDFs, not just text — enables richer tool interactions.                                                  |
| **Streaming function calling**    | Stream partial function call arguments during tool use, reducing time-to-first-tool-call.                                                          |
| **Thought signatures**            | Stricter validation in multi-turn function calling — the model must acknowledge tool results via thought signatures before producing final output. |

## Recommended Settings by Use Case

| Use Case                             | Temperature | Thinking Level    | Max Output Tokens |
| ------------------------------------ | ----------- | ----------------- | ----------------- |
| Casual chat / small talk             | **1.0**     | `MINIMAL`         | Default           |
| Trip planning (tool loop)            | **1.0**     | `MINIMAL`         | Default           |
| Trip planning (structured output)    | **1.0**     | `MINIMAL`         | Default           |
| High-throughput non-critical queries | **1.0**     | `LOW` / `MINIMAL` | 50–100            |
| Precise / deterministic answers      | **1.0**     | `MEDIUM` / `HIGH` | Default           |

> **⚠️ Temperature Warning:** Google recommends keeping `temperature` at **1.0** for all Gemini 3 models. Gemini 3's reasoning capabilities are optimized for the default — setting it below 1.0 may cause looping, degraded reasoning, or unexpected behavior, particularly on complex mathematical or logical tasks. **Do not lower temperature for "more determinism"** on Gemini 3; use `seed` instead for reproducible output.
