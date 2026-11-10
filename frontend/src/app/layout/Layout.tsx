import { Outlet } from "react-router-dom";

import { Footer } from "@/app/layout/Footer";
import { Navbar } from "@/app/layout/Navbar";

/** Navbar + page + footer. `footer={false}` for full-screen pages such as the Geo-Portal. */
export function Layout({ footer = true }: { footer?: boolean }) {
  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <Navbar />
      <main id="main">
        <Outlet />
      </main>
      {footer && <Footer />}
    </>
  );
}
