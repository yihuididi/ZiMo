import { useCallback, useMemo, useReducer } from "react";

import { ApiError, getRoom, submitCommand } from "../../lib/api";
import { errorMessage } from "../../lib/errors";
import {
  RoomSessionStorageError,
  updateStoredInviteToken,
  type RoomSession,
} from "../../lib/session";
import type { OpaqueActionDescriptor, PublicRoomView } from "../../lib/types";
import {
  initialRoomCommandState,
  roomCommandReducer,
  type CommandOperation,
  type PendingCommand,
} from "./roomCommandReducer";

interface UseRoomCommandsOptions {
  roomId: string;
  session: RoomSession;
  acceptView: (view: PublicRoomView) => boolean;
  getCurrentView: () => PublicRoomView | null;
  onSessionChange: (session: RoomSession) => void;
  onSessionEnded: () => void;
  onSessionRevoked: () => void;
}

export function useRoomCommands({
  roomId,
  session,
  acceptView,
  getCurrentView,
  onSessionChange,
  onSessionEnded,
  onSessionRevoked,
}: UseRoomCommandsOptions) {
  const [state, dispatch] = useReducer(
    roomCommandReducer,
    initialRoomCommandState,
  );

  const executeOperation = useCallback(
    async (operation: CommandOperation) => {
      const { command } = operation;
      try {
        const response = await submitCommand(
          roomId,
          session.playerToken,
          command,
        );
        if (response.type === "sessionEnded") {
          onSessionEnded();
          return;
        }
        acceptView(response.view);
        const currentView = getCurrentView();
        const currentViewer = currentView?.players.find(
          (player) => player.playerId === currentView.viewerPlayerId,
        );
        if (
          response.inviteToken &&
          currentView?.revision === response.view.revision &&
          currentViewer?.role === "HOST"
        ) {
          try {
            const updated = updateStoredInviteToken(
              session,
              response.inviteToken,
            );
            onSessionChange(updated);
          } catch (reason) {
            if (reason instanceof RoomSessionStorageError) {
              dispatch({
                type: "retryRequired",
                actionId: command.actionId,
                commandId: command.commandId,
                message:
                  "The invitation was rotated, but this browser could not store it. Enable persistent browser storage, then retry safely to recover the same invitation.",
              });
              return;
            }
            throw reason;
          }
        }
        dispatch({
          type: "succeeded",
          actionId: command.actionId,
          commandId: command.commandId,
        });
      } catch (reason) {
        if (reason instanceof ApiError && reason.status === 409) {
          try {
            acceptView(await getRoom(roomId, session.playerToken));
            dispatch({
              type: "conflictRefreshed",
              actionId: command.actionId,
              commandId: command.commandId,
              message: "The room changed first. Your view has been refreshed.",
            });
          } catch (refreshReason) {
            if (
              refreshReason instanceof ApiError &&
              refreshReason.status === 401
            ) {
              onSessionRevoked();
              return;
            }
            dispatch({
              type: "terminalFailed",
              actionId: command.actionId,
              commandId: command.commandId,
              message: errorMessage(refreshReason),
            });
          }
          return;
        }
        if (reason instanceof ApiError && reason.status === 401) {
          onSessionRevoked();
          return;
        }
        if (reason instanceof ApiError && reason.status < 500) {
          dispatch({
            type: "terminalFailed",
            actionId: command.actionId,
            commandId: command.commandId,
            message: reason.message,
          });
          return;
        }
        dispatch({
          type: "retryRequired",
          actionId: command.actionId,
          commandId: command.commandId,
          message: "The result is unknown. You can retry this command safely.",
        });
      }
    },
    [
      acceptView,
      getCurrentView,
      onSessionChange,
      onSessionEnded,
      onSessionRevoked,
      roomId,
      session,
    ],
  );

  const runAction = useCallback(
    (action: OpaqueActionDescriptor) => {
      const view = getCurrentView();
      if (!view || !action.enabled || state.byActionId[action.actionId]) return;
      const command: PendingCommand = {
        commandId: crypto.randomUUID(),
        expectedRevision: view.revision,
        actionId: action.actionId,
      };
      const operation: CommandOperation = {
        command,
        label: action.label,
        slot: action.presentationSlot,
        phase: "submitting",
      };
      dispatch({ type: "begin", operation });
      void executeOperation(operation);
    },
    [executeOperation, getCurrentView, state.byActionId],
  );

  const retryAction = useCallback(
    (actionId: string) => {
      const operation = state.byActionId[actionId];
      if (!operation || operation.phase !== "retryable") return;
      dispatch({
        type: "retryBegin",
        actionId,
        commandId: operation.command.commandId,
      });
      void executeOperation(operation);
    },
    [executeOperation, state.byActionId],
  );

  const recoverableOperations = useMemo(
    () =>
      Object.values(state.byActionId).filter(
        (operation): operation is Extract<
          CommandOperation,
          { phase: "retryable" }
        > => operation.phase === "retryable",
      ),
    [state.byActionId],
  );

  return {
    operationsByActionId: state.byActionId,
    feedback: state.feedback,
    recoverableOperations,
    runAction,
    retryAction,
  };
}
