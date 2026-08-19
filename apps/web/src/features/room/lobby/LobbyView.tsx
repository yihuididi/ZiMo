import { BrandLink } from "../../../components/BrandLink";
import { PageHeading } from "../../../components/PageHeading";
import { useDocumentTitle } from "../../../hooks/useDocumentTitle";
import type { ConnectionStatus } from "../../../hooks/useRoomSocket";
import type { RoomSession } from "../../../lib/session";
import type {
  OpaqueActionDescriptor,
  PublicRoomView,
} from "../../../lib/types";
import type {
  CommandFeedback,
  CommandOperation,
} from "../roomCommandReducer";
import { InvitePanel } from "./InvitePanel";
import { RoomActions } from "./RoomActions";
import { RulesCard } from "./RulesCard";
import { SeatList } from "./SeatList";

interface LobbyViewProps {
  roomId: string;
  session: RoomSession;
  view: PublicRoomView;
  connection: { status: ConnectionStatus; error: string | null };
  roomWarning: string | null;
  operationsByActionId: Record<string, CommandOperation>;
  recoverableOperations: Array<
    Extract<CommandOperation, { phase: "retryable" }>
  >;
  feedback: CommandFeedback[];
  onRunAction: (action: OpaqueActionDescriptor) => void;
  onRetryAction: (actionId: string) => void;
}

export function LobbyView({
  roomId,
  session,
  view,
  connection,
  roomWarning,
  operationsByActionId,
  recoverableOperations,
  feedback,
  onRunAction,
  onRetryAction,
}: LobbyViewProps) {
  useDocumentTitle(`Room lobby · ZiMo Mahjong`);

  const invitationAction = view.actions.find(
    (action) => action.presentationSlot === "invitation",
  );
  const roomActions = view.actions.filter(
    (action) => action.presentationSlot === "roomActions",
  );

  return (
    <main className="page-shell lobby-shell">
      <header className="lobby-header">
        <BrandLink />
        <div className={`connection-status ${connection.status}`} role="status">
          <span aria-hidden="true" />
          {connection.status === "connected"
            ? "Live"
            : connection.status === "offline"
              ? "Offline"
              : connection.status === "connecting"
                ? "Connecting"
                : "Reconnecting"}
        </div>
      </header>

      <div className="lobby-title-row">
        <div>
          <p className="eyebrow">Private table · Revision {view.revision}</p>
          <PageHeading focusOnMount>Room lobby</PageHeading>
          <p>
            Settle in while the table fills. The host starts when everyone is
            ready.
          </p>
        </div>
        <span className="room-status">
          {view.status.replaceAll("_", " ")}
        </span>
      </div>

      <div className="lobby-layout">
        <div className="main-column">
          <section className="panel seats-panel" aria-labelledby="seats-heading">
            <div className="panel-heading">
              <div>
                <p className="step-label">Four-seat table</p>
                <h2 id="seats-heading">Players</h2>
              </div>
              <span>
                {view.seats.filter((seat) => seat.occupant).length}/4 seated
              </span>
            </div>
            <SeatList view={view} />
          </section>

          {view.status === "IN_MATCH" &&
            view.game?.status === "PENDING_SETUP" && (
              <section
                className="panel setup-panel"
                aria-labelledby="setup-heading"
              >
                <p className="step-label">Match created</p>
                <h2 id="setup-heading">
                  Match started; gameplay arrives in Milestone 3
                </h2>
                <p>
                  Gameplay is intentionally not available in this preview. The
                  room roster and rules are now locked.
                </p>
              </section>
            )}

          <RulesCard view={view} />
        </div>

        <aside className="side-column">
          {invitationAction && view.status !== "IN_MATCH" && (
            <InvitePanel
              roomId={roomId}
              inviteToken={session.inviteToken}
              action={invitationAction}
              operation={operationsByActionId[invitationAction.actionId]}
              onRunAction={onRunAction}
            />
          )}

          <RoomActions
            actions={roomActions}
            operationsByActionId={operationsByActionId}
            recoverableOperations={recoverableOperations}
            feedback={feedback}
            roomWarning={roomWarning}
            connectionError={connection.error}
            connectionStatus={connection.status}
            onRunAction={onRunAction}
            onRetryAction={onRetryAction}
          />
        </aside>
      </div>
    </main>
  );
}
