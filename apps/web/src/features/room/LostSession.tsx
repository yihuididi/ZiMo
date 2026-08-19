import { Link } from "react-router-dom";

import { BrandLink } from "../../components/BrandLink";
import { PageHeading } from "../../components/PageHeading";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";

export function LostSession({ roomId }: { roomId: string }) {
  useDocumentTitle("Room session unavailable · ZiMo Mahjong");

  return (
    <main className="page-shell narrow-shell">
      <BrandLink />
      <section className="entry-card lost-card" aria-labelledby="lost-heading">
        <span className="lost-icon" aria-hidden="true">
          ↻
        </span>
        <PageHeading id="lost-heading" focusOnMount>
          This room session is unavailable
        </PageHeading>
        <p>
          No valid player access is stored on this device. It may have been
          removed, revoked, or cleared from this browser.
        </p>
        <p className="room-reference">Room {roomId}</p>
        <Link className="primary-action link-action" to="/">
          Return home
        </Link>
      </section>
    </main>
  );
}
