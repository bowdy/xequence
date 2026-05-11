import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Xequence",
  description: "Twitter DM sequences",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <Link href="/" className="brand">
            Xequence
          </Link>
          <nav>
            <Link href="/contacts">Contacts</Link>
            <Link href="/sequences">Sequences</Link>
            <Link href="/enrollments">Enrollments</Link>
            <Link href="/messages">Messages</Link>
          </nav>
        </header>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
