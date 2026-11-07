from enum import StrEnum

import pytest

from alcedo import (
    InvalidStateTransitionError,
    StateActionGuard,
    StateActionNotAllowedError,
    StateFlow,
    StateTransition,
)


class TaskState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskTrigger(StrEnum):
    START = "start"
    COMPLETE = "complete"
    FAIL = "fail"
    RETRY = "retry"


class TaskAction(StrEnum):
    CANCEL = "cancel"
    RATE = "rate"


def test_state_flow_transitions_and_queries() -> None:
    flow = StateFlow(
        (
            StateTransition(TaskState.CREATED, TaskTrigger.START, TaskState.RUNNING),
            StateTransition(
                TaskState.RUNNING, TaskTrigger.COMPLETE, TaskState.COMPLETED
            ),
            StateTransition(TaskState.RUNNING, TaskTrigger.FAIL, TaskState.FAILED),
            StateTransition(TaskState.FAILED, TaskTrigger.RETRY, TaskState.RUNNING),
        )
    )

    assert flow.can_transition(TaskState.CREATED, TaskTrigger.START)
    assert flow.transition(TaskState.CREATED, TaskTrigger.START) == TaskState.RUNNING
    assert flow.allowed_triggers(TaskState.RUNNING) == (
        TaskTrigger.COMPLETE,
        TaskTrigger.FAIL,
    )
    assert flow.get_next_state(TaskState.COMPLETED, TaskTrigger.START) is None

    with pytest.raises(InvalidStateTransitionError):
        flow.transition(TaskState.COMPLETED, TaskTrigger.START)


def test_state_action_guard() -> None:
    guard = StateActionGuard(
        {
            TaskAction.CANCEL: {TaskState.CREATED, TaskState.RUNNING},
            TaskAction.RATE: {TaskState.COMPLETED},
        }
    )

    assert guard.is_allowed(TaskState.RUNNING, TaskAction.CANCEL)
    assert guard.allowed_actions(TaskState.COMPLETED) == (TaskAction.RATE,)
    guard.ensure_allowed(TaskState.COMPLETED, TaskAction.RATE)

    with pytest.raises(StateActionNotAllowedError):
        guard.ensure_allowed(TaskState.RUNNING, TaskAction.RATE)


def test_duplicate_transition_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate transition"):
        StateFlow(
            (
                StateTransition(
                    TaskState.CREATED, TaskTrigger.START, TaskState.RUNNING
                ),
                StateTransition(
                    TaskState.CREATED, TaskTrigger.START, TaskState.FAILED
                ),
            )
        )
