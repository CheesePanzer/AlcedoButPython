from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

TState = TypeVar("TState", bound=Enum)
TTrigger = TypeVar("TTrigger", bound=Enum)
TAction = TypeVar("TAction", bound=Enum)


class InvalidStateTransitionError(RuntimeError, Generic[TState, TTrigger]):
    def __init__(self, state: TState, trigger: TTrigger) -> None:
        self.state = state
        self.trigger = trigger
        super().__init__(
            f"trigger {_enum_value(trigger)!r} is not allowed in state "
            f"{_enum_value(state)!r}"
        )


class StateActionNotAllowedError(RuntimeError, Generic[TState, TAction]):
    def __init__(self, state: TState, action: TAction) -> None:
        self.state = state
        self.action = action
        super().__init__(
            f"action {_enum_value(action)!r} is not allowed in state "
            f"{_enum_value(state)!r}"
        )


@dataclass(frozen=True, slots=True)
class StateTransition(Generic[TState, TTrigger]):
    source: TState
    trigger: TTrigger
    target: TState


class StateFlow(Generic[TState, TTrigger]):
    def __init__(
        self,
        transitions: Sequence[StateTransition[TState, TTrigger]],
    ) -> None:
        transition_map: dict[tuple[TState, TTrigger], TState] = {}
        allowed_map: dict[TState, list[TTrigger]] = {}
        for transition in transitions:
            key = (transition.source, transition.trigger)
            if key in transition_map:
                raise ValueError(
                    f"duplicate transition for state {_enum_value(transition.source)!r} "
                    f"and trigger {_enum_value(transition.trigger)!r}"
                )
            transition_map[key] = transition.target
            allowed_map.setdefault(transition.source, []).append(transition.trigger)
        self._transitions = transition_map
        self._allowed = {
            state: tuple(triggers) for state, triggers in allowed_map.items()
        }

    def can_transition(self, state: TState, trigger: TTrigger) -> bool:
        return (state, trigger) in self._transitions

    def get_next_state(self, state: TState, trigger: TTrigger) -> TState | None:
        return self._transitions.get((state, trigger))

    def transition(self, state: TState, trigger: TTrigger) -> TState:
        next_state = self.get_next_state(state, trigger)
        if next_state is None:
            raise InvalidStateTransitionError(state, trigger)
        return next_state

    def allowed_triggers(self, state: TState) -> tuple[TTrigger, ...]:
        return self._allowed.get(state, ())


class StateActionGuard(Generic[TState, TAction]):
    def __init__(
        self,
        rules: Mapping[TAction, Iterable[TState]],
    ) -> None:
        self._rules = {
            action: frozenset(states) for action, states in rules.items()
        }

    def is_allowed(self, state: TState, action: TAction) -> bool:
        return state in self._rules.get(action, frozenset())

    def ensure_allowed(self, state: TState, action: TAction) -> None:
        if not self.is_allowed(state, action):
            raise StateActionNotAllowedError(state, action)

    def allowed_actions(self, state: TState) -> tuple[TAction, ...]:
        return tuple(
            action for action, states in self._rules.items() if state in states
        )


def _enum_value(value: Enum) -> object:
    return value.value
