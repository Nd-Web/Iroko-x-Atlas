"use client";

/**
 * useSector — reads/writes the active compliance sector (network | financial).
 *
 * Persisted to localStorage so it survives navigation between the compliance
 * pages, and synced across mounted consumers in the same tab (via a custom
 * window event) and across tabs (via the native `storage` event).
 */

import { useCallback, useEffect, useState } from "react";
import {
  DEFAULT_SECTOR,
  SECTOR_EVENT,
  SECTOR_STORAGE_KEY,
  Sector,
  isSector,
} from "@/lib/sector";

export function useSector(): [Sector, (s: Sector) => void] {
  const [sector, setSectorState] = useState<Sector>(DEFAULT_SECTOR);

  useEffect(() => {
    const stored = localStorage.getItem(SECTOR_STORAGE_KEY);
    if (isSector(stored)) setSectorState(stored);

    const onStorage = (e: StorageEvent) => {
      if (e.key === SECTOR_STORAGE_KEY && isSector(e.newValue)) {
        setSectorState(e.newValue);
      }
    };
    const onCustom = (e: Event) => {
      const detail = (e as CustomEvent<Sector>).detail;
      if (isSector(detail)) setSectorState(detail);
    };

    window.addEventListener("storage", onStorage);
    window.addEventListener(SECTOR_EVENT, onCustom as EventListener);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(SECTOR_EVENT, onCustom as EventListener);
    };
  }, []);

  const setSector = useCallback((s: Sector) => {
    setSectorState(s);
    localStorage.setItem(SECTOR_STORAGE_KEY, s);
    window.dispatchEvent(new CustomEvent<Sector>(SECTOR_EVENT, { detail: s }));
  }, []);

  return [sector, setSector];
}
