import { Link } from "react-router-dom";

import { BrandLink } from "../components/BrandLink";
import { PageHeading } from "../components/PageHeading";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

export function NotFoundPage() {
  useDocumentTitle("Page not found · ZiMo Mahjong");

  return (
    <main className="page-shell narrow-shell">
      <BrandLink />
      <section className="entry-card lost-card">
        <PageHeading focusOnMount>Page not found</PageHeading>
        <Link className="primary-action link-action" to="/">
          Return home
        </Link>
      </section>
    </main>
  );
}
