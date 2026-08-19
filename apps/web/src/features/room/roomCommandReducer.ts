import type { OpaqueActionDescriptor } from "../../lib/types";

export interface PendingCommand {
  commandId: string;
  actionId: string;
  expectedRevision: number;
}

interface CommandOperationBase {
  command: PendingCommand;
  label: string;
  slot: OpaqueActionDescriptor["presentationSlot"];
}

export type CommandOperation =
  | (CommandOperationBase & { phase: "submitting" })
  | (CommandOperationBase & {
      phase: "retryable";
      retryMessage: string;
    });

export interface CommandFeedback {
  commandId: string;
  actionId: string;
  label: string;
  slot: OpaqueActionDescriptor["presentationSlot"];
  kind: "error" | "notice";
  message: string;
}

export interface RoomCommandState {
  byActionId: Record<string, CommandOperation>;
  feedback: CommandFeedback[];
}

export const initialRoomCommandState: RoomCommandState = {
  byActionId: {},
  feedback: [],
};

export type RoomCommandEvent =
  | { type: "begin"; operation: CommandOperationBase }
  | { type: "retryBegin"; actionId: string; commandId: string }
  | { type: "succeeded"; actionId: string; commandId: string }
  | {
      type: "retryRequired";
      actionId: string;
      commandId: string;
      message: string;
    }
  | {
      type: "terminalFailed";
      actionId: string;
      commandId: string;
      message: string;
    }
  | {
      type: "conflictRefreshed";
      actionId: string;
      commandId: string;
      message: string;
    }
  | { type: "reset" };

function matchingOperation(
  state: RoomCommandState,
  actionId: string,
  commandId: string,
): CommandOperation | null {
  const operation = state.byActionId[actionId];
  return operation?.command.commandId === commandId ? operation : null;
}

function withoutOperation(
  operations: Record<string, CommandOperation>,
  actionId: string,
): Record<string, CommandOperation> {
  const updated = { ...operations };
  delete updated[actionId];
  return updated;
}

function settleWithFeedback(
  state: RoomCommandState,
  event: Extract<
    RoomCommandEvent,
    { type: "terminalFailed" | "conflictRefreshed" }
  >,
): RoomCommandState {
  const operation = matchingOperation(
    state,
    event.actionId,
    event.commandId,
  );
  if (!operation) return state;
  const feedback: CommandFeedback = {
    commandId: event.commandId,
    actionId: event.actionId,
    label: operation.label,
    slot: operation.slot,
    kind: event.type === "terminalFailed" ? "error" : "notice",
    message: event.message,
  };
  return {
    byActionId: withoutOperation(state.byActionId, event.actionId),
    feedback: [
      ...state.feedback.filter(
        (item) =>
          item.actionId !== event.actionId ||
          item.commandId !== event.commandId,
      ),
      feedback,
    ],
  };
}

export function roomCommandReducer(
  state: RoomCommandState,
  event: RoomCommandEvent,
): RoomCommandState {
  switch (event.type) {
    case "begin": {
      const { actionId } = event.operation.command;
      if (state.byActionId[actionId]) return state;
      return {
        byActionId: {
          ...state.byActionId,
          [actionId]: { ...event.operation, phase: "submitting" },
        },
        feedback: state.feedback.filter((item) => item.actionId !== actionId),
      };
    }
    case "retryBegin": {
      const operation = matchingOperation(
        state,
        event.actionId,
        event.commandId,
      );
      if (!operation || operation.phase !== "retryable") return state;
      return {
        byActionId: {
          ...state.byActionId,
          [event.actionId]: {
            command: operation.command,
            label: operation.label,
            slot: operation.slot,
            phase: "submitting",
          },
        },
        feedback: state.feedback.filter(
          (item) => item.actionId !== event.actionId,
        ),
      };
    }
    case "succeeded": {
      if (!matchingOperation(state, event.actionId, event.commandId)) {
        return state;
      }
      return {
        ...state,
        byActionId: withoutOperation(state.byActionId, event.actionId),
      };
    }
    case "retryRequired": {
      const operation = matchingOperation(
        state,
        event.actionId,
        event.commandId,
      );
      if (!operation) return state;
      return {
        ...state,
        byActionId: {
          ...state.byActionId,
          [event.actionId]: {
            command: operation.command,
            label: operation.label,
            slot: operation.slot,
            phase: "retryable",
            retryMessage: event.message,
          },
        },
      };
    }
    case "terminalFailed":
    case "conflictRefreshed":
      return settleWithFeedback(state, event);
    case "reset":
      return initialRoomCommandState;
  }
}
