import { describe, expect, it } from "vitest";

import {
  initialRoomCommandState,
  roomCommandReducer,
  type CommandOperation,
  type RoomCommandState,
} from "./roomCommandReducer";

function operation(
  actionId: string,
  commandId: string,
  label = actionId,
): CommandOperation {
  return {
    phase: "submitting",
    command: { actionId, commandId, expectedRevision: 7 },
    label,
    slot: "roomActions",
  };
}

function begin(
  state: RoomCommandState,
  nextOperation: CommandOperation,
): RoomCommandState {
  return roomCommandReducer(state, {
    type: "begin",
    operation: nextOperation,
  });
}

describe("roomCommandReducer", () => {
  it("keeps one action recoverable while another action succeeds", () => {
    let state = begin(
      initialRoomCommandState,
      operation("ready", "command-ready", "Ready"),
    );
    state = begin(
      state,
      operation("invite", "command-invite", "Rotate invitation"),
    );
    state = roomCommandReducer(state, {
      type: "retryRequired",
      actionId: "ready",
      commandId: "command-ready",
      message: "Unknown result",
    });
    state = roomCommandReducer(state, {
      type: "succeeded",
      actionId: "invite",
      commandId: "command-invite",
    });

    expect(state.byActionId.ready).toMatchObject({
      phase: "retryable",
      retryMessage: "Unknown result",
      command: { commandId: "command-ready" },
    });
    expect(state.byActionId.invite).toBeUndefined();
  });

  it("retains two ambiguous commands and retries either exact command", () => {
    let state = begin(
      initialRoomCommandState,
      operation("ready", "command-ready", "Ready"),
    );
    state = begin(
      state,
      operation("invite", "command-invite", "Rotate invitation"),
    );
    for (const [actionId, commandId] of [
      ["ready", "command-ready"],
      ["invite", "command-invite"],
    ] as const) {
      state = roomCommandReducer(state, {
        type: "retryRequired",
        actionId,
        commandId,
        message: `${actionId} is unknown`,
      });
    }

    expect(
      Object.values(state.byActionId).filter(
        (entry) => entry.phase === "retryable",
      ),
    ).toHaveLength(2);

    state = roomCommandReducer(state, {
      type: "retryBegin",
      actionId: "ready",
      commandId: "command-ready",
    });
    expect(state.byActionId.ready).toEqual(
      operation("ready", "command-ready", "Ready"),
    );
    expect(state.byActionId.invite.phase).toBe("retryable");
  });

  it("does not let any stale settlement change a newer same-action command", () => {
    const current = begin(
      initialRoomCommandState,
      operation("ready", "command-current", "Ready"),
    );
    const staleEvents = [
      {
        type: "succeeded" as const,
        actionId: "ready",
        commandId: "command-stale",
      },
      {
        type: "retryRequired" as const,
        actionId: "ready",
        commandId: "command-stale",
        message: "Unknown",
      },
      {
        type: "terminalFailed" as const,
        actionId: "ready",
        commandId: "command-stale",
        message: "Rejected",
      },
    ];

    for (const event of staleEvents) {
      const state = roomCommandReducer(current, event);
      expect(state).toBe(current);
      expect(state.byActionId.ready.command.commandId).toBe("command-current");
    }
  });

  it("settles only the failed action and preserves its presentation metadata", () => {
    let state = begin(
      initialRoomCommandState,
      operation("ready", "command-ready", "Ready"),
    );
    state = begin(
      state,
      operation("invite", "command-invite", "Rotate invitation"),
    );
    state = roomCommandReducer(state, {
      type: "terminalFailed",
      actionId: "ready",
      commandId: "command-ready",
      message: "Not allowed",
    });

    expect(state.byActionId.ready).toBeUndefined();
    expect(state.byActionId.invite).toBeDefined();
    expect(state.feedback).toEqual([
      expect.objectContaining({
        commandId: "command-ready",
        actionId: "ready",
        label: "Ready",
        kind: "error",
        message: "Not allowed",
      }),
    ]);
  });

  it("turns a refreshed conflict into notice feedback", () => {
    let state = begin(
      initialRoomCommandState,
      operation("ready", "command-ready", "Ready"),
    );
    state = roomCommandReducer(state, {
      type: "conflictRefreshed",
      actionId: "ready",
      commandId: "command-ready",
      message: "Refreshed",
    });

    expect(state.byActionId.ready).toBeUndefined();
    expect(state.feedback[0]).toMatchObject({
      kind: "notice",
      message: "Refreshed",
    });
  });

  it("preserves unrelated feedback when another action starts or retries", () => {
    let state = begin(
      initialRoomCommandState,
      operation("finished", "command-finished", "Finished action"),
    );
    state = roomCommandReducer(state, {
      type: "terminalFailed",
      actionId: "finished",
      commandId: "command-finished",
      message: "Finished action failed",
    });
    state = begin(
      state,
      operation("ready", "command-ready", "Ready"),
    );
    state = roomCommandReducer(state, {
      type: "retryRequired",
      actionId: "ready",
      commandId: "command-ready",
      message: "Ready result unknown",
    });
    state = roomCommandReducer(state, {
      type: "retryBegin",
      actionId: "ready",
      commandId: "command-ready",
    });

    expect(state.feedback).toEqual([
      expect.objectContaining({
        actionId: "finished",
        message: "Finished action failed",
      }),
    ]);
  });
});
