# Architecture — Version 1

Version 1 treats the LLM as the game master, the rule engine, the memory and the narrator. The room description, the three puzzles and the secret solution are all in one system prompt.

## Components

| Component | File | Responsibility |
|---|---|---|
| Gradio interface | `app_v1.py` | Chat input, chat history, restart button and status message. |
| Game loop | `escape_room/v1_game.py` | Appends player messages, converts history to Gemini turns, detects `[ESCAPED]`. |
| Gemini client | `escape_room/llm.py` | Sends the system prompt and full chat history to the model. |
| System prompt | `SYSTEM_PROMPT` in `v1_game.py` | Contains the room, rules and complete solution. |

## Component diagram

```mermaid
flowchart LR
    P[Player] -->|natural language| UI[Gradio UI<br/>app_v1.py]
    UI -->|full chat history| GAME[v1_game.py<br/>history + ESCAPED detection]
    GAME -->|system prompt + history| LLM[Gemini<br/>Game Master]
    LLM -->|narration| GAME
    GAME -->|updated chat| UI
    UI --> P
    PROMPT[System prompt<br/>room, rules, secret solution] -.-> LLM
```

## Turn sequence

```mermaid
sequenceDiagram
    actor Player
    participant UI as Gradio UI
    participant Game as v1_game.py
    participant LLM as Gemini
    Player->>UI: "examine the bookshelf"
    UI->>Game: take_turn(chat, text)
    Game->>LLM: system prompt + entire chat history
    LLM-->>Game: narration, maybe with [ESCAPED]
    Game->>Game: strip token, set escaped flag
    Game-->>UI: updated chat + escaped
    UI-->>Player: narration
```

## What works

- Fast to build and easy to change the story.
- Natural language feels flexible.
- The model can improvise descriptions and hints.

## Why it is unreliable

| Weakness | Consequence |
|---|---|
| No structured state | The model can forget an opened drawer or contradict an earlier action. |
| Rules are prompt text | A persuasive player can talk the model out of the rules. |
| Solution is in the prompt | The model may reveal codes early or accept a correct code before the puzzles are solved. |
| No inventory check | The model may let the player use a key that was never collected. |
| No object whitelist | The model may invent a chandelier, a safe or a second door. |
| Escape is a magic token | Detection depends on the model remembering to emit `[ESCAPED]`. |
| Long history | Important facts get diluted as the conversation grows. |

These weaknesses are intentional: Version 1 is the baseline that Version 2 improves. See `docs/test_cases.md` and `scripts/v1_probe.py` for reproduction steps.
