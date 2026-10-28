import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CrisisGrid - Tactical Command",
  description: "Autonomous Multimodal Disaster Triage, Infrastructure Assessment & Emergency Dispatch Agent",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
