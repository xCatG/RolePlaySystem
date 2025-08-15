"""
==============================================================================
== Architectural Note: Why this agent lives in `chat/` vs `dev_agents/`     ==
==============================================================================
This file contains the core production logic for orchestrating a role-play
session. It is intentionally placed in the `role_play/chat/` directory
alongside other core chat components like `handler.py` and `chat_logger.py`.

The `dev_agents/` directory is reserved for agents and tools that are used
for development-time inspection and debugging (e.g., listing scenarios,
viewing character prompts).

While it can be convenient to place all agent code in a single location for
debugging with the ADK toolkit, in this case, maintaining a clear separation
between production application logic and development/testing utilities is
the priority for long-term maintainability.

Please keep this file within the `chat/` module.
==============================================================================
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Union, AsyncGenerator, Optional

from google.adk.agents import BaseAgent, LlmAgent, Event, InvocationContext
from google.genai import types

# --- Import your typed models from a central location ---
# It's good practice to place these in a file like `role_play/common/models.py`
try:
    from .models import SideEffect, ObserverOutput, Progress, State
except ImportError:
    # Define placeholders if models.py is not updated yet
    SideEffect = Dict[str, Any]
    ObserverOutput = Dict[str, Any]
    Progress = Dict[str, Any]
    State = Dict[str, Any]


# --- Lightweight rule-based tracker (Your implementation) ---
@dataclass
class ScriptTracker:
    """A placeholder for the script tracker."""
    # ... (Your ScriptTracker code here) ...
    rules: List[Any] # In a real implementation, this would be a list of ScriptRule objects

    def check(self, messages: List[Dict[str, str]], progress: Progress) -> Optional[ObserverOutput]:
        """Checks user messages against predefined script rules."""
        # Placeholder implementation
        return None

# --- Side-effect executor (Your implementation) ---
class SideEffectExecutor:
    # This logic now modifies the ADK InvocationContext
    def apply(self, ctx: InvocationContext, effects: List[SideEffect]) -> None:
        if not effects:
            return
        for eff in effects:
            t = eff.get("type")
            # Set side effects for the UI to consume
            ctx.session.state.setdefault("side_effects", []).append(eff)
            if t == "collect_input":
                # Set interrupt flag for the game loop
                ctx.session.state["interrupt"] = True
            elif t == "retrieve_kb":
                ctx.session.state.setdefault("kb_ctx", []).append({"snippet": f"Result for {eff['query']}"})
            # ... (other side effect logic) ...

# --- LLM Observer (As an ADK LlmAgent) ---
# This agent's purpose is to return structured JSON, which ADK handles natively.
observer_agent = LlmAgent(
    name="observer",
    model="gemini-1.5-flash-latest", # A fast model is good for this
    instruction=(
        "You are the Director. Analyze the provided transcript and scene_state, then produce a JSON object with: "
        "'actor_hint' (guidance for the performer, <=80 words), 'side_effects' (optional list of system commands), "
        "'progress_update' (optional), and 'risk' level. Never speak in-character."
    ),
    output_schema=ObserverOutput, # ADK uses the TypedDict for structured output
    output_key="observer_output"  # The result will be saved here in the session state
)

# --- Actor (As an ADK LlmAgent) ---
# This agent's instruction is a template that will be filled from session state.
actor_agent = LlmAgent(
    name="actor",
    model="gemini-1.5-pro-latest", # A more powerful model for high-quality performance
    instruction=(
        "You are the Performer. Stay strictly in character based on your profile. "
        "Your current director's hint is: '{actor_hint}'. "
        "Respond to the last user message based on this hint. "
        "Do not mention the UI or director. Output only your line of dialogue."
    ),
    output_key="actor_text"
)

# --- The Main Orchestrator (As an ADK CustomAgent) ---
class Orchestrator(BaseAgent):
    def __init__(self, name: str, tracker: ScriptTracker, observer: LlmAgent, actor: LlmAgent, executor: SideEffectExecutor):
        # The observer and actor are sub-agents for organizational purposes
        super().__init__(name=name, sub_agents=[observer, actor])
        self.tracker = tracker
        self.observer = observer
        self.actor = actor
        self.exec = executor

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """This is the main "game loop" for each conversational turn."""
        state: State = ctx.session.state
        
        # 1. Clear transient state from the previous turn
        state["side_effects"] = []
        state["interrupt"] = False

        # 2. Lightweight rules check first
        messages = state.get("messages", [])
        progress = state.get("progress", {"scene": "scene", "step": 0, "objectives": []})
        rule_out = self.tracker.check(messages, progress)
        obs_out: Optional[ObserverOutput] = None

        # 3. Decide if the LLM Observer is needed
        needs_observer = (rule_out is None) # Add your other heuristics here
        
        if needs_observer:
            # The runner will execute the observer agent. We just need to process the result.
            async for event in self.observer.run_async(ctx):
                if event.is_final_response():
                    # The result is automatically placed in state['observer_output'] by the agent's output_key
                    obs_out = state.get("observer_output")
                    break # We have the result, no need to continue the event loop
        else:
            obs_out = rule_out
        
        # 4. Process the decision and execute side-effects
        if obs_out:
            if effects := obs_out.get("side_effects"):
                self.exec.apply(ctx, effects)
            if prog_update := obs_out.get("progress_update"):
                state["progress"] = prog_update
            state["actor_hint"] = obs_out.get("actor_hint", "Respond naturally.")
        
        # 5. Check for UI Interrupt
        if state.get("interrupt"):
            # An interrupt was requested (e.g., to show a form).
            # We yield a final event for this turn to let the UI take over.
            # The 'actor_text' might be empty, but the UI will see the side_effects.
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="Interrupted for UI action.")])
            )
            return

        # 6. If no interrupt, call the Actor to generate the user-facing response
        async for event in self.actor.run_async(ctx):
            if event.is_final_response():
                # The actor's dialogue is the primary output of the turn.
                # The final response text is in event.content.parts[0].text
                # and also in state['actor_text']
                
                # Add the actor's response to the persistent message history
                messages.append({"role": "assistant", "content": state.get("actor_text", "")})
                state["messages"] = messages
                
                yield event # Pass the actor's response to the user
                break