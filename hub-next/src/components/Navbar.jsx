"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";

const INTERNAL = [
  { href: "/docs/overview", label: "AI Capabilities" },
  { href: "/docs/projects/pitchbook-attio", label: "Systems", match: "/docs/projects" },
  { href: "/docs/research", label: "Research" },
  { href: "/docs/admin", label: "Admin" },
];

export default function Navbar() {
  const pathname = usePathname() || "";
  // The public investor view hides the internal tabs (mirrors the old hub).
  const investorView = pathname.startsWith("/investors");

  const isActive = (item) =>
    pathname === item.href || (item.match && pathname.startsWith(item.match)) ||
    (item.href !== "/docs/overview" && pathname.startsWith(item.href));

  return (
    <nav className="navbar">
      <div className="navbar__inner">
        <Link href="/" aria-label="ID8 Investments">
          <Image className="navbar__logo" src="/img/logo_charcoal.png" alt="ID8" width={60} height={15} priority />
        </Link>
        {!investorView && (
          <div className="navbar__links">
            {INTERNAL.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`navbar__link${isActive(item) ? " navbar__link--active" : ""}`}
              >
                {item.label}
              </Link>
            ))}
          </div>
        )}
        <div className="navbar__spacer" />
        <Link href="/investors" className="navbar__link">Investor View</Link>
      </div>
    </nav>
  );
}
