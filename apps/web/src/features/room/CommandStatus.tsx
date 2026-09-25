import type { ConnectionStatus } from "../../hooks/useRoomSocket";
import type {
  CommandFeedback,
  CommandOperation,
} from "./roomCommandReducer";

interface CommandStatusProps {
  recoverableOperations: Array<
    Extract<CommandOperation, { phase: "retryable" }>
  >;
  feedback: CommandFeedback[];
  roomWarning: string | null;
  connectionError: string | null;
  connectionStatus: ConnectionStatus;
  onRetryAction: (actionId: string) => void;
}

export function CommandStatus({
  recoverableOperations,
  feedback,
  roomWarning,
  connectionError,
  connectionStatus,
  onRetryAction,
}: CommandStatusProps) {
  const hasCommandError =
    roomWarning !== null ||
    recoverableOperations.length > 0 ||
    feedback.some((item) => item.kind === "error");

  return (
    <div className="command-status">
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
    </div>
  );
}
