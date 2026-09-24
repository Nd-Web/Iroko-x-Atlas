"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import styles from "./pilot.module.css";

type Availability = {
  timezone: string;
  slot_minutes: number;
  business_hours: string;
  slots: string[];
};

type Booking = {
  id: string;
  slot_start: string;
  slot_end: string;
  timezone: string;
};

const PHONE_CODES = [
  ["NG", "+234"], ["GH", "+233"], ["KE", "+254"], ["ZA", "+27"],
  ["UG", "+256"], ["TZ", "+255"], ["RW", "+250"], ["CM", "+237"],
  ["CI", "+225"], ["SN", "+221"], ["GB", "+44"], ["US/CA", "+1"],
  ["AE", "+971"], ["FR", "+33"], ["DE", "+49"], ["Other", "+"],
];

const WAT_DATE = new Intl.DateTimeFormat("en-NG", {
  timeZone: "Africa/Lagos", weekday: "short", day: "numeric", month: "short",
});
const WAT_LONG = new Intl.DateTimeFormat("en-NG", {
  timeZone: "Africa/Lagos", weekday: "long", day: "numeric", month: "long", year: "numeric",
  hour: "2-digit", minute: "2-digit", hour12: true,
});
const WAT_TIME = new Intl.DateTimeFormat("en-NG", {
  timeZone: "Africa/Lagos", hour: "2-digit", minute: "2-digit", hour12: true,
});
const dayKey = (iso: string) => new Intl.DateTimeFormat("en-CA", {
  timeZone: "Africa/Lagos", year: "numeric", month: "2-digit", day: "2-digit",
}).format(new Date(iso));

export default function RequestPilotPage() {
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [loadingSlots, setLoadingSlots] = useState(true);
  const [selectedDay, setSelectedDay] = useState("");
  const [selectedSlot, setSelectedSlot] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [slotsError, setSlotsError] = useState("");
  const [booking, setBooking] = useState<Booking | null>(null);
  const [phoneCode, setPhoneCode] = useState("+234");

  const loadAvailability = useCallback(async () => {
    setLoadingSlots(true);
    setSlotsError("");
    try {
      const response = await fetch("/api/pilot/availability", { cache: "no-store" });
      if (!response.ok) throw new Error("Could not load available times.");
      const data: Availability = await response.json();
      setAvailability(data);
      const firstDay = data.slots[0] ? dayKey(data.slots[0]) : "";
      setSelectedDay((current) => current && data.slots.some((slot) => dayKey(slot) === current) ? current : firstDay);
    } catch {
      setSlotsError("We couldn't reach the booking calendar. The service may be waking up.");
    } finally {
      setLoadingSlots(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadAvailability(), 0);
    return () => window.clearTimeout(timer);
  }, [loadAvailability]);

  const days = useMemo(() => {
    const grouped = new Map<string, string[]>();
    for (const slot of availability?.slots ?? []) {
      const key = dayKey(slot);
      grouped.set(key, [...(grouped.get(key) ?? []), slot]);
    }
    return [...grouped.entries()];
  }, [availability]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSlot) {
      setError("Please choose an onboarding call time.");
      return;
    }
    setSubmitting(true);
    setError("");
    const data = new FormData(event.currentTarget);
    const localPhone = String(data.get("phone") ?? "").trim();
    const payload = {
      full_name: data.get("full_name"),
      work_email: data.get("work_email"),
      phone: `${phoneCode}${localPhone.replace(/^0+/, "")}`,
      company_name: data.get("company_name"),
      job_title: data.get("job_title"),
      company_type: data.get("company_type"),
      country: data.get("country"),
      pilot_goal: data.get("pilot_goal") || null,
      consent_to_contact: data.get("consent_to_contact") === "on",
      slot_start: selectedSlot,
    };

    try {
      const response = await fetch("/api/pilot/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await response.json();
      if (response.status === 409) {
        setSelectedSlot("");
        await loadAvailability();
        throw new Error(body.detail?.message ?? "That time was just booked. Please choose another.");
      }
      if (!response.ok) {
        const detail = Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail;
        throw new Error(typeof detail === "string" ? detail : "We couldn't submit your request. Please check the form and try again.");
      }
      setBooking(body);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (booking) {
    return (
      <div className={styles.page}>
        <Header />
        <main className={styles.successWrap}>
          <div className={styles.successIcon}>✓</div>
          <p className={styles.eyebrow}>Pilot request confirmed</p>
          <h1>You&apos;re booked.</h1>
          <p className={styles.successCopy}>We&apos;ve received your request and reserved your onboarding call.</p>
          <div className={styles.bookingCard}>
            <span>30-minute onboarding call</span>
            <strong>{WAT_LONG.format(new Date(booking.slot_start))} WAT</strong>
          </div>
          <p className={styles.successNote}>Your free 30-day pilot starts from this call. A confirmation has been sent to your work email.</p>
          <Link className={styles.backLink} href="/">Back to Iroko AI</Link>
        </main>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <Header />
      <main className={styles.main}>
        <section className={styles.intro}>
          <p className={styles.eyebrow}><span /> Free 30-day pilot</p>
          <h1>Put Iroko AI to work<br />inside your organisation.</h1>
          <p>Tell us about your team, then reserve a 30-minute onboarding call. Your pilot begins from that call—no payment details required.</p>
          <div className={styles.benefits}>
            <div><b>01</b><span>30 days of hands-on access</span></div>
            <div><b>02</b><span>Guided onboarding with our team</span></div>
            <div><b>03</b><span>Built around your real use case</span></div>
          </div>
        </section>

        <form className={styles.formCard} onSubmit={submit}>
          <Section number="01" title="About you">
            <div className={styles.twoCols}>
              <Field label="Full name"><input name="full_name" autoComplete="name" required minLength={2} placeholder="Ada Okonkwo" /></Field>
              <Field label="Work email"><input name="work_email" type="email" autoComplete="email" required placeholder="ada@company.com" /></Field>
            </div>
            <div className={styles.twoCols}>
              <Field label="Phone number">
                <div className={styles.phoneField}>
                  <select aria-label="Country calling code" value={phoneCode} onChange={(event) => setPhoneCode(event.target.value)}>
                    {PHONE_CODES.map(([country, code]) => <option key={`${country}-${code}`} value={code}>{country} {code}</option>)}
                  </select>
                  <input name="phone" type="tel" autoComplete="tel-national" required minLength={7} placeholder="801 234 5678" />
                </div>
              </Field>
              <Field label="Job title"><input name="job_title" autoComplete="organization-title" required minLength={2} placeholder="Head of Compliance" /></Field>
            </div>
          </Section>

          <Section number="02" title="Your company">
            <div className={styles.twoCols}>
              <Field label="Company name"><input name="company_name" autoComplete="organization" required minLength={2} placeholder="Your organisation" /></Field>
              <Field label="Company type">
                <select name="company_type" required defaultValue=""><option value="" disabled>Select company type</option><option>Microfinance Bank</option><option>Fintech</option><option>Other</option></select>
              </Field>
            </div>
            <Field label="Country"><input name="country" autoComplete="country-name" required minLength={2} placeholder="Nigeria" /></Field>
            <Field label="What would you like the pilot to help you solve?" optional>
              <textarea name="pilot_goal" maxLength={1000} rows={4} placeholder="Briefly describe the workflow, documents, or compliance challenge you want to explore." />
            </Field>
          </Section>

          <Section number="03" title="Book your onboarding call" last>
            <div className={styles.calendarMeta}><span>30 minutes</span><span>Mon–Fri</span><span>{availability?.business_hours ?? "09:00–17:00"} WAT</span></div>
            {loadingSlots ? <div className={styles.calendarState}>Loading available times…</div> : slotsError ? (
              <div className={styles.calendarState}><span>{slotsError}</span><button type="button" onClick={() => void loadAvailability()}>Try again</button></div>
            ) : days.length === 0 ? (
              <div className={styles.calendarState}><span>No times are currently available. Please check again shortly.</span><button type="button" onClick={() => void loadAvailability()}>Refresh times</button></div>
            ) : (
              <>
                <div className={styles.dayList} aria-label="Available dates">
                  {days.map(([key, slots]) => (
                    <button key={key} type="button" className={selectedDay === key ? styles.dayActive : ""} onClick={() => { setSelectedDay(key); setSelectedSlot(""); }}>
                      {WAT_DATE.format(new Date(slots[0]))}
                    </button>
                  ))}
                </div>
                <div className={styles.timeGrid} aria-label="Available times">
                  {(days.find(([key]) => key === selectedDay)?.[1] ?? []).map((slot) => (
                    <button key={slot} type="button" className={selectedSlot === slot ? styles.timeActive : ""} onClick={() => { setSelectedSlot(slot); setError(""); }}>
                      {WAT_TIME.format(new Date(slot))}
                    </button>
                  ))}
                </div>
              </>
            )}
            <p className={styles.notice}>Times are shown in West Africa Time (UTC+1). Booking requires at least 24 hours&apos; notice.</p>
          </Section>

          <label className={styles.consent}>
            <input name="consent_to_contact" type="checkbox" required />
            <span>I agree to be contacted by Iroko AI about this pilot request.</span>
          </label>
          {error && <div className={styles.error} role="alert">{error}</div>}
          <button className={styles.submit} type="submit" disabled={submitting || loadingSlots || !selectedSlot}>
            {submitting ? "Booking your call…" : "Request free 30-day pilot"}<span>→</span>
          </button>
          <p className={styles.secure}>Your details are used only to arrange and support your pilot.</p>
        </form>
      </main>
    </div>
  );
}

function Header() {
  return (
    <header className={styles.header}>
      <div className={styles.headerInner}>
        <Link href="/" className={styles.brand} aria-label="Iroko AI home">
          <svg viewBox="0 0 42 42" aria-hidden="true">
            <rect width="42" height="42" rx="13" fill="#176b49" />
            <path d="M13 29V13h8.2c5.3 0 8.8 2.8 8.8 7.3 0 4.6-3.5 7.5-8.8 7.5H17.8" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="14.5" cy="29" r="2" fill="white" />
          </svg>
          <span>iroko<span className={styles.brandAi}>ai</span><small>Document Intelligence</small></span>
        </Link>
        <Link href="/login" className={styles.signIn}>Sign in</Link>
      </div>
    </header>
  );
}

function Section({ number, title, children, last = false }: { number: string; title: string; children: React.ReactNode; last?: boolean }) {
  return <section className={`${styles.section} ${last ? styles.last : ""}`}><div className={styles.sectionTitle}><span>{number}</span><h2>{title}</h2></div><div className={styles.sectionBody}>{children}</div></section>;
}

function Field({ label, optional = false, children }: { label: string; optional?: boolean; children: React.ReactNode }) {
  return <label className={styles.field}><span>{label}{optional && <em>Optional</em>}</span>{children}</label>;
}
