// Construct the timezone formatter once, not once per slot on every refresh.
const WAT_DAY = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Africa/Lagos", year: "numeric", month: "2-digit", day: "2-digit",
});

export const pilotDayKey = (iso: string) => WAT_DAY.format(new Date(iso));

/** Preserve the API's day/time order without repeatedly copying each day. */
export function groupPilotSlots(slots: readonly string[]): [string, string[]][] {
  const grouped = new Map<string, string[]>();
  for (const slot of slots) {
    const key = pilotDayKey(slot);
    const day = grouped.get(key);
    if (day) day.push(slot);
    else grouped.set(key, [slot]);
  }
  return [...grouped.entries()];
}
