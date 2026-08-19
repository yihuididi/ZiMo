import { useId } from "react";

import type { ConnectionStatus } from "../../../hooks/useRoomSocket";
import type { OpaqueActionDescriptor } from "../../../lib/types";
import type {
  CommandFeedback,
  CommandOperation,
} from "../roomCommandReducer";

interface ActionEntryProps {
  action: OpaqueActionDescriptor;
  operation: CommandOperation | undefined;
  onRunAction: (action: OpaqueActionDescriptor) => void;
}

function ActionEntry({ action, operation, onRunAction }: ActionEntryProps) {
  const disabledReasonId = useId();
  const isSubmitting = operation?.phase === "submitting";
  return (
    <div className="action-entry">
      <button
        aria-busy={isSubmitting || undefined}
        aria-describedby={
          action.disabledReason ? disabledReasonId : undefined
        }
        className={`descriptor-action tone-${action.tone ?? "neutral"}`}
        type="button"
        disabled={!action.enabled || Boolean(operation)}
        onClick={() => onRunAction(action)}
      >
        {isSubmitting ? "Working…" : action.label}
      </button>
      {action.disabledReason && (
        <p className="disabled-reason" id={disabledReasonId}>
          {action.disabledReason}
        </p>
      )}
    </div>
  );
}

interface RoomActionsProps {
  actions: OpaqueActionDescriptor[];
  operationsByActionId: Record<string, CommandOperation>;
  recoverableOperations: Array<
    Extract<CommandOperation, { phase: "retryable" }>
  >;
  feedback: CommandFeedback[];
  roomWarning: string | null;
  connectionError: string | null;
  connectionStatus: ConnectionStatus;
  onRunAction: (action: OpaqueActionDescriptor) => void;
  onRetryAction: (actionId: string) => void;
}

export function RoomActions({
  actions,
  operationsByActionId,
  recoverableOperations,
  feedback,
  roomWarning,
  connectionError,
  connectionStatus,
  onRunAction,
  onRetryAction,
}: RoomActionsProps) {
  const hasCommandError =
    roomWarning !== null ||
    recoverableOperations.length > 0 ||
    feedback.some((item) => item.kind === "error");

  return (
    <section className="panel actions-panel" aria-labelledby="actions-heading">
      <p className="step-label">Available now</p>
      <h2 id="actions-heading">Room actions</h2>
      {actions.length === 0 ? (
        <p className="fine-print">No actions are available right now.</p>
      ) : (
        <div className="action-stack">
          {actions.map((action) => (
            <ActionEntry
              action={action}
              operation={operationsByActionId[action.actionId]}
              onRunAction={onRunAction}
              key={action.actionId}
            />
          ))}
        </div>
      )}

      {recoverableOperations.map((operation) => (
        <div className="command-recovery" key={operation.command.commandId}>
          <p className="message error" role="alert">
            {operation.retryMessage}
          </p>
          <button
            aria-label={`Retry ${operation.label} safely`}
            className="retry-action"
            type="button"
            onClick={() => onRetryAction(operation.command.actionId)}
          >
            Retry safely
          </button>
        </div>
      ))}

      {feedback.map((item) => (
        <p
          className={`message ${item.kind}`}
          role={item.kind === "error" ? "alert" : "status"}
          key={`${item.kind}-${item.actionId}-${item.commandId}`}
        >
          {item.message}
        </p>
      ))}
      {roomWarning && (
        <p className="message error" role="alert">
          {roomWarning}
        </p>
      )}
      {connectionError && !hasCommandError && (
        <p className="message error" role="status">
          {connectionStatus === "offline"
            ? `Offline. ${connectionError}`
            : connectionError}
        </p>
      )}
    </section>
  );
}
