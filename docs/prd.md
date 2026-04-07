# Product Requirements Document (PRD)
**Project Name:** Gemma-Powered Minecraft Ops Dashboard
**Version:** 1.0 (MVP)

## 1. Objective
Build a local-first, lightweight web dashboard to manage a Vanilla Minecraft server. The defining feature is the integration of "Gemma Assistant", an AI Operator assistant powered by the local Gemma 4 E2B model. Gemma Assistant reads the live server chat and can safely execute operator commands (like `/give` or `/time set`) via strict JSON tool-calling, protected by Python-layer failsafes.

## 2. Core Philosophy & Constraints
* **Local First:** Zero API costs, zero latency, absolute privacy.
* **1-Click Appliance:** The app must manage its own bundled `server.jar` in an isolated directory. No attaching to pre-existing external servers for V1.
* **Database-Free:** File-based state management only (`.json` files).
* **Vanilla First:** V1 strictly targets official Mojang Vanilla server software (no plugin staging yet).

## 3. Key Features

### 3.1. The 1-Click Installer Setup (`install.sh` / `install.bat`)
* Automatically check for and install Python 3.11+.
* Set up a `.venv` and install `requirements.txt`.
* Detect the OS, silently install Ollama if missing, and run `ollama pull gemma4:e2b`.
* Download the latest Vanilla `server.jar` into the `app/minecraft_server/` directory.
* Generate a `.env` file with secure random hashes for session middleware.

### 3.2. Minecraft Server Management
* **Process Control:** Wrap the Java process inside a `tmux` session (primary) with a `nohup` fallback.
* **Command Injection (Write):** Execute all commands (user UI or AI generated) using `tmux send-keys -t <session> "<command>" C-m`.
* **Live Feed (Read):** Tail `latest.log` using byte-offset tracking. Push chunks over WebSocket to the UI.

### 3.3. AI Operator Assistant (Gemma Assistant)
* **LLM Engine:** Local Ollama endpoint (`http://localhost:11434/v1/chat/completions`) requesting `gemma4:e2b`.
* **Context Loop:** Feed parsed, chronological `latest.log` chat events into a sliding in-memory `deque` to serve as the LLM's context window.
* **Privilege Routing:**
    * *Non-Ops:* Routed to a standard Chat System Prompt (no JSON tools provided).
    * *Ops:* Routed to an Agentic System Prompt equipped with strict JSON tool schemas for Vanilla commands.
* **Action-Observation:** After Gemma Assistant executes a tool via `tmux`, the backend must capture the resulting output from `latest.log` and feed it back to the LLM to confirm execution success/failure.
* **Safety Failsafes:** JSON tool outputs must pass through Python-level Regex blacklists (e.g., blocking `/stop`, `/deop`) before ever hitting `tmux`.

## 4. Out of Scope for Version 1
* Remote tunneling (Cloudflare/ngrok).
* Plugin ecosystem support (PaperMC/Spigot).
* React/Vue frontend builds (sticking to Vanilla JS).
