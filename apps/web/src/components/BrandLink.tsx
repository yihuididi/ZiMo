import { Link } from "react-router-dom";

export function BrandLink() {
  return (
    <Link className="brand-link" to="/">
      <span aria-hidden="true">四</span>
      <span>ZiMo Mahjong</span>
    </Link>
  );
}
