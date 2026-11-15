"use client";
import { useEffect, useState } from "react";
import { LoaderCircle, Plus, Trash2, X } from "lucide-react";
import { api } from "@/lib/api";
import type { DeliveryRules, SiteSettings } from "@/lib/types";
import { Button } from "./ui/button";
import { InlineError } from "./states";
import styles from "./owner-dashboard.module.css";

type Row = { prefixes: string; estimate: string };

function rowsOf(rules: DeliveryRules | null): Row[] {
  return (rules?.estimates ?? []).map((e) => ({
    prefixes: e.prefixes.join(", "),
    estimate: e.estimate,
  }));
}

/** Owner settings for one site: details, routing, delivery estimates, removal. */
export function SiteSettingsPanel({
  token,
  host,
  onChanged,
  onRemoved,
  onClose,
}: {
  token: string;
  host: string;
  onChanged: (settings: SiteSettings) => void;
  onRemoved: () => void;
  onClose: () => void;
}) {
  const [site, setSite] = useState<SiteSettings | null>(null);
  const [details, setDetails] = useState({ name: "", origin: "" });
  const [delivery, setDelivery] = useState({
    default_estimate: "",
    free_delivery_over: "",
    pin_pattern: "^\\d{6}$",
  });
  const [rows, setRows] = useState<Row[]>([]);
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  useEffect(() => {
    api
      .siteSettings(token, host)
      .then((value) => {
        setSite(value);
        setDetails({ name: value.name, origin: value.origin });
        const rules = value.delivery_rules;
        setDelivery({
          default_estimate: rules?.default_estimate ?? "",
          free_delivery_over:
            rules?.free_delivery_over == null
              ? ""
              : String(rules.free_delivery_over),
          pin_pattern: rules?.pin_pattern ?? "^\\d{6}$",
        });
        setRows(rowsOf(rules));
      })
      .catch((e: Error) => setError(e.message));
  }, [token, host]);

  async function run(label: string, action: () => Promise<void>) {
    setBusy(label);
    setError("");
    setSaved("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy("");
    }
  }

  const apply = (value: SiteSettings, message: string) => {
    setSite(value);
    onChanged(value);
    setSaved(message);
  };

  return (
    <section
      className={`${styles.shell} ${styles.section}`}
      aria-labelledby="settings-title"
    >
      <div className={`${styles.card} ${styles.cardBody}`}>
        <div className={styles.cardHead}>
          <h2 id="settings-title">Site settings</h2>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X size={14} aria-hidden="true" /> Close
          </Button>
        </div>
        {!site ? (
          error ? (
            <InlineError>{error}</InlineError>
          ) : (
            <p className={styles.hint} role="status">
              Loading settings…
            </p>
          )
        ) : (
          <div className={styles.settings}>
            <form
              className={styles.settingsGroup}
              onSubmit={(event) => {
                event.preventDefault();
                void run("details", async () =>
                  apply(
                    await api.updateSite(token, host, details),
                    "Site details saved.",
                  ),
                );
              }}
            >
              <h3>Details</h3>
              <p className={styles.hint}>
                Public host <span className={styles.host}>{site.host}</span> is
                the routing key and cannot change; add a new site instead.
              </p>
              <div className={styles.addGrid}>
                <label>
                  Site name
                  <input
                    className="field mt-2"
                    value={details.name}
                    onChange={(e) =>
                      setDetails({ ...details, name: e.target.value })
                    }
                    required
                    maxLength={200}
                  />
                </label>
                <label>
                  Origin
                  <input
                    className="field mt-2"
                    type="url"
                    value={details.origin}
                    onChange={(e) =>
                      setDetails({ ...details, origin: e.target.value })
                    }
                    required
                    maxLength={2048}
                    spellCheck={false}
                  />
                </label>
              </div>
              <div>
                <Button size="sm" disabled={busy !== ""}>
                  {busy === "details" && (
                    <LoaderCircle
                      size={14}
                      className="animate-spin"
                      aria-hidden="true"
                    />
                  )}
                  Save details
                </Button>
              </div>
            </form>

            <div className={styles.settingsGroup}>
              <h3>Agent lane routing</h3>
              <label className={styles.toggle}>
                <input
                  type="checkbox"
                  checked={site.routing_enabled}
                  disabled={busy !== ""}
                  onChange={(e) => {
                    const enabled = e.target.checked;
                    void run("routing", async () =>
                      apply(
                        await api.updateSite(token, host, {
                          routing_enabled: enabled,
                        }),
                        enabled
                          ? "AI agents get the agent lane again."
                          : "Routing paused. Everyone gets your original site.",
                      ),
                    );
                  }}
                />
                <span>
                  <strong>Serve the agent lane to AI agents</strong>
                  <span className={styles.hint}>
                    When off, every request goes to your site unchanged. Agent
                    requests are still logged so the dashboard stays accurate.
                  </span>
                </span>
              </label>
            </div>

            <form
              className={styles.settingsGroup}
              onSubmit={(event) => {
                event.preventDefault();
                const rules: DeliveryRules = {
                  pin_pattern: delivery.pin_pattern,
                  default_estimate: delivery.default_estimate,
                  free_delivery_over:
                    delivery.free_delivery_over === ""
                      ? null
                      : Number(delivery.free_delivery_over),
                  estimates: rows
                    .filter((r) => r.prefixes.trim() && r.estimate.trim())
                    .map((r) => ({
                      prefixes: r.prefixes
                        .split(",")
                        .map((p) => p.trim())
                        .filter(Boolean),
                      estimate: r.estimate.trim(),
                    })),
                };
                void run("delivery", async () =>
                  apply(
                    await api.setDelivery(token, host, rules),
                    "Delivery estimates saved.",
                  ),
                );
              }}
            >
              <h3>Delivery estimates</h3>
              <p className={styles.hint}>
                Agents get these answers from the check_delivery action. They
                come only from you, never from your site’s login-gated checker.
              </p>
              <div className={styles.addGrid}>
                <label>
                  Default estimate
                  <input
                    className="field mt-2"
                    value={delivery.default_estimate}
                    onChange={(e) =>
                      setDelivery({
                        ...delivery,
                        default_estimate: e.target.value,
                      })
                    }
                    placeholder="3–5 working days"
                    required
                    maxLength={80}
                  />
                </label>
                <label>
                  Free delivery over (optional)
                  <input
                    className="field mt-2"
                    type="number"
                    min={0}
                    step="any"
                    value={delivery.free_delivery_over}
                    onChange={(e) =>
                      setDelivery({
                        ...delivery,
                        free_delivery_over: e.target.value,
                      })
                    }
                  />
                </label>
                <label>
                  PIN code pattern
                  <input
                    className="field mt-2 font-mono"
                    value={delivery.pin_pattern}
                    onChange={(e) =>
                      setDelivery({ ...delivery, pin_pattern: e.target.value })
                    }
                    required
                    maxLength={60}
                    spellCheck={false}
                  />
                </label>
              </div>
              <fieldset className={styles.rows}>
                <legend>Faster areas</legend>
                {rows.map((row, index) => (
                  <div key={index} className={styles.rowItem}>
                    <label>
                      <span className="sr-only">
                        PIN prefixes, row {index + 1}
                      </span>
                      <input
                        className="field"
                        value={row.prefixes}
                        placeholder="PIN prefixes, e.g. 11, 40, 56"
                        onChange={(e) =>
                          setRows(
                            rows.map((r, i) =>
                              i === index
                                ? { ...r, prefixes: e.target.value }
                                : r,
                            ),
                          )
                        }
                      />
                    </label>
                    <label>
                      <span className="sr-only">Estimate, row {index + 1}</span>
                      <input
                        className="field"
                        value={row.estimate}
                        placeholder="2–3 working days"
                        maxLength={80}
                        onChange={(e) =>
                          setRows(
                            rows.map((r, i) =>
                              i === index
                                ? { ...r, estimate: e.target.value }
                                : r,
                            ),
                          )
                        }
                      />
                    </label>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-label={`Remove row ${index + 1}`}
                      onClick={() =>
                        setRows(rows.filter((_, i) => i !== index))
                      }
                    >
                      <X size={14} aria-hidden="true" />
                    </Button>
                  </div>
                ))}
                <div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={rows.length >= 50}
                    onClick={() =>
                      setRows([...rows, { prefixes: "", estimate: "" }])
                    }
                  >
                    <Plus size={14} aria-hidden="true" /> Add an area
                  </Button>
                </div>
              </fieldset>
              <div className={styles.laneActions}>
                <Button size="sm" disabled={busy !== ""}>
                  {busy === "delivery" && (
                    <LoaderCircle
                      size={14}
                      className="animate-spin"
                      aria-hidden="true"
                    />
                  )}
                  Save delivery estimates
                </Button>
                {site.delivery_rules && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={busy !== ""}
                    onClick={() =>
                      void run("delivery-clear", async () => {
                        apply(
                          await api.setDelivery(token, host, null),
                          "Delivery estimates removed.",
                        );
                        setRows([]);
                      })
                    }
                  >
                    Remove estimates
                  </Button>
                )}
              </div>
            </form>

            <form
              className={`${styles.settingsGroup} ${styles.danger}`}
              onSubmit={(event) => {
                event.preventDefault();
                void run("remove", async () => {
                  await api.removeSite(token, host);
                  onRemoved();
                });
              }}
            >
              <h3>Remove site</h3>
              <p className={styles.hint}>
                Deletes this site with its agent logs, sessions, agent lane
                versions, jobs and QA results. Point your DNS back to your
                origin first. This cannot be undone.
              </p>
              <label>
                Type <span className={styles.host}>{site.host}</span> to confirm
                <input
                  className="field mt-2"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                />
              </label>
              <div>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy !== "" || confirm.trim() !== site.host}
                >
                  <Trash2 size={14} aria-hidden="true" /> Remove site
                </Button>
              </div>
            </form>
          </div>
        )}
        {site && error && (
          <div className="mt-4">
            <InlineError>{error}</InlineError>
          </div>
        )}
        {saved && (
          <p
            className={`${styles.jobLine} mt-4`}
            data-tone="success"
            role="status"
          >
            {saved}
          </p>
        )}
      </div>
    </section>
  );
}
