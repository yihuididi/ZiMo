import { BrandLink } from "../../../components/BrandLink";
import { PageHeading } from "../../../components/PageHeading";
import { useDocumentTitle } from "../../../hooks/useDocumentTitle";
import type { ConnectionStatus } from "../../../hooks/useRoomSocket";

export function PreparingTable({
  connectionStatus,
}: {
  connectionStatus: ConnectionStatus;
}) {
  useDocumentTitle("Preparing table · ZiMo Mahjong");
  return (
    <main className="page-shell narrow-shell preparing-table-shell">
      <BrandLink />
      <section className="panel preparing-table-panel" aria-live="polite">
        <p className="step-label">Match created</p>
        <PageHeading focusOnMount>Preparing the table</PageHeading>
        <p>
          The server is shuffling and dealing the authoritative 148-tile wall.
          This view will update automatically.
        </p>
        <div className="preparing-pulse" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        {connectionStatus !== "connected" && (
          <p className="fine-print">The live connection is {connectionStatus}.</p>
        )}
      </section>
    </main>
  );
}
