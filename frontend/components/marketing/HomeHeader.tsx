"use client";

import { useState, type ReactNode } from "react";
import s from "./homepage.module.css";

/** Only the mobile menu needs hydration; page content stays server-rendered. */
export default function HomeHeader({ brand, navigation, actions, mobileNavigation }: {
  brand: ReactNode;
  navigation: ReactNode;
  actions: ReactNode;
  mobileNavigation: ReactNode;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  return <header className={s.header}>
    <div className={s.navWrap}>
      {brand}
      <nav aria-label="Main navigation" className={s.desktopNav}>{navigation}</nav>
      <div className={s.navActions}>
        {actions}
        <button className={s.menuToggle} aria-label={menuOpen ? "Close navigation" : "Open navigation"}
          aria-expanded={menuOpen} aria-controls="mobile-navigation" onClick={() => setMenuOpen(!menuOpen)}>
          {menuOpen ? "✕" : "☰"}
        </button>
      </div>
    </div>
    {menuOpen && <nav id="mobile-navigation" aria-label="Mobile navigation" className={s.mobileNav}
      onClick={() => setMenuOpen(false)}>{mobileNavigation}</nav>}
  </header>;
}
