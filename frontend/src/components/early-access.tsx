"use client";

import { useId, useState } from "react";
import type { FormEvent } from "react";
import { ArrowRight, Check, LoaderCircle } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "./ui/button";
import styles from "./landing.module.css";

function hostOf(value: string) {
  return value
    .trim()
    .replace(/^https?:\/\//i, "")
    .replace(/^www\./i, "")
    .split(/[/?#]/)[0];
}

/** Agent lane early access: email and website, stored for a hand-run setup. */
export function EarlyAccessForm() {
  const id = useId();
  const [email, setEmail] = useState("");
  const [website, setWebsite] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "done">("idle");
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state === "sending") return;
    const trap = new FormData(event.currentTarget).get("company");
    setState("sending");
    setError("");
    try {
      await api.requestEarlyAccess(email, website, String(trap ?? ""));
      setState("done");
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Couldn’t send your request. Please try again.",
      );
      setState("idle");
    }
  }

  if (state === "done")
    return (
      <div className={styles.earlyDone} role="status">
        <span aria-hidden="true">
          <Check size={16} strokeWidth={3} />
        </span>
        <p>
          <strong>You’re on the list.</strong> We’ll email {email.trim()} to
          plan the agent lane for {hostOf(website)}. Meanwhile,{" "}
          <a href="#scan">run a free scan</a> to see where agents get stuck
          today.
        </p>
      </div>
    );

  return (
    <form className={styles.earlyForm} onSubmit={submit} noValidate={false}>
      <label htmlFor={`${id}-email`}>Work email</label>
      <input
        id={`${id}-email`}
        type="email"
        name="email"
        required
        autoComplete="email"
        placeholder="you@company.com"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
      />
      <label htmlFor={`${id}-website`}>Your website</label>
      <input
        id={`${id}-website`}
        type="text"
        name="website"
        required
        inputMode="url"
        autoComplete="url"
        placeholder="yourdomain.com"
        value={website}
        onChange={(event) => setWebsite(event.target.value)}
      />
      {/* Left empty by people; bots that fill every field are ignored. */}
      <div className={styles.trap} aria-hidden="true">
        <label htmlFor={`${id}-company`}>Company</label>
        <input
          id={`${id}-company`}
          type="text"
          name="company"
          tabIndex={-1}
          autoComplete="off"
        />
      </div>
      <Button
        type="submit"
        variant="lime"
        size="lg"
        className="mt-1 w-full"
        disabled={state === "sending"}
      >
        {state === "sending" ? (
          <LoaderCircle size={16} className="animate-spin" />
        ) : null}
        Request early access <ArrowRight size={16} />
      </Button>
      {error && (
        <p className={styles.earlyError} role="alert">
          {error}
        </p>
      )}
      <p className={styles.earlyNote}>
        No payment now. We reply by email to plan your setup.
      </p>
    </form>
  );
}
