"use client";

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { BookOpen, RotateCcw, Truck } from "lucide-react";
import styles from "./agent-race.module.css";

type SceneState = {
  loaded?: boolean;
  popup?: boolean;
  question?: boolean;
  picked?: boolean;
  blocked?: boolean;
  opened?: boolean;
  footer?: boolean;
  read?: boolean;
};
type Beat = {
  at: number;
  time: string;
  caption: string;
  shot?: boolean;
  cursor?: [number, number];
  set?: SceneState;
};
type LaneItem = { at: number; node: ReactNode };
type Task = {
  id: string;
  label: string;
  question: string;
  url: string;
  scene: "product" | "listing" | "policy";
  original: Beat[];
  originalEnd: number;
  originalSeconds: number;
  originalResult: { label: string; text: string };
  shots: number;
  lane: LaneItem[];
  laneCaptions: Beat[];
  laneEnd: number;
  laneSeconds: number;
  laneResult: string;
  laneSteps: number;
};

const SIZES = ["UK 7", "UK 8", "UK 9", "UK 10", "UK 11"];
const LISTING = [
  ["Trail Runner", "₹2,799"],
  ["City Walker", "₹1,999"],
  ["Court Classic", "₹3,499"],
  ["Aero Racer", "₹6,299"],
  ["Monsoon Guard", "₹3,199"],
  ["Studio Flex", "₹2,499"],
  ["Summit Hiker", "₹4,599"],
  ["Easy Slide", "₹899"],
];

// The original side replays the demo store's documented problems (JavaScript-only
// content, an offer pop-up, unlabeled sizes, delivery behind a login); its timings and
// outcomes are illustrative. Every agent-lane answer is the demo store's real one.
const TASKS: Task[] = [
  {
    id: "stock",
    label: "Stock and delivery",
    question: "Is the Trail Runner in stock in UK 9, and can it reach 560001?",
    url: "northstar.example/product/trail-runner",
    scene: "product",
    original: [
      {
        at: 0,
        time: "0:01",
        caption: "Opens the page. It’s blank: products load with JavaScript.",
        shot: true,
        cursor: [62, 70],
      },
      {
        at: 850,
        time: "0:06",
        caption: "Waits for scripts and takes another screenshot.",
        shot: true,
        set: { loaded: true },
      },
      {
        at: 1400,
        time: "0:09",
        caption: "A “10% off” pop-up covers the page.",
        shot: true,
        cursor: [84, 27],
        set: { popup: true },
      },
      {
        at: 1950,
        time: "0:14",
        caption: "Closes it and scrolls to the sizes.",
        cursor: [54, 52],
        set: { popup: false },
      },
      {
        at: 2500,
        time: "0:19",
        caption: "Five size buttons, none labeled. Guessing…",
        shot: true,
        set: { question: true },
      },
      {
        at: 3050,
        time: "0:27",
        caption: "Clicks one. Nothing confirms which size.",
        set: { picked: true },
      },
      {
        at: 3600,
        time: "0:33",
        caption: "Delivery needs a login. Stuck.",
        shot: true,
        cursor: [30, 86],
        set: { blocked: true },
      },
    ],
    originalEnd: 4200,
    originalSeconds: 41,
    originalResult: {
      label: "Unsure.",
      text: "“It may be available in some sizes. I couldn’t check delivery.”",
    },
    shots: 5,
    lane: [
      {
        at: 400,
        node: <p className={styles.call}>GET /product/trail-runner.md</p>,
      },
      {
        at: 650,
        node: (
          <div className={styles.sizeChips}>
            {SIZES.map((size) => (
              <span
                key={size}
                data-hit={size === "UK 9" || undefined}
                data-out={size === "UK 10" || undefined}
              >
                {size}
              </span>
            ))}
          </div>
        ),
      },
      { at: 900, node: <p className={styles.call}>check_delivery(560001)</p> },
      {
        at: 1100,
        node: (
          <p className={styles.card}>
            <Truck size={14} /> 2–3 working days · free over ₹1,500
          </p>
        ),
      },
    ],
    laneCaptions: [
      { at: 0, time: "0:00", caption: "Gets the question." },
      { at: 400, time: "0:01", caption: "Reads /product/trail-runner.md." },
      { at: 900, time: "0:02", caption: "Calls check_delivery(560001)." },
    ],
    laneEnd: 1300,
    laneSeconds: 2,
    laneResult:
      "“Yes. UK 9 is in stock at ₹2,799 and reaches 560001 in 2–3 working days, with free delivery.”",
    laneSteps: 2,
  },
  {
    id: "cheapest",
    label: "Cheapest running shoe",
    question: "What’s your cheapest running shoe?",
    url: "northstar.example",
    scene: "listing",
    original: [
      {
        at: 0,
        time: "0:01",
        caption: "Opens the store. The grid is empty until scripts run.",
        shot: true,
        cursor: [50, 60],
      },
      {
        at: 850,
        time: "0:06",
        caption: "Products appear. Nothing says which are for running.",
        shot: true,
        set: { loaded: true },
      },
      {
        at: 1400,
        time: "0:09",
        caption: "A “10% off” pop-up covers the grid.",
        shot: true,
        cursor: [84, 27],
        set: { popup: true },
      },
      {
        at: 1950,
        time: "0:14",
        caption: "Closes it and opens products to find their category.",
        cursor: [20, 46],
        set: { popup: false },
      },
      {
        at: 2600,
        time: "0:24",
        caption: "Three product pages later, still comparing.",
        shot: true,
        cursor: [70, 46],
        set: { opened: true },
      },
      {
        at: 3250,
        time: "0:35",
        caption: "Gives up and picks the cheapest shoe it saw.",
        cursor: [45, 46],
        set: { picked: true },
      },
    ],
    originalEnd: 3900,
    originalSeconds: 38,
    originalResult: {
      label: "Wrong.",
      text: "“The City Walker, at ₹1,999.” It’s an everyday shoe, not a running shoe.",
    },
    shots: 4,
    lane: [
      {
        at: 400,
        node: (
          <p className={styles.call}>search_products(&quot;running&quot;)</p>
        ),
      },
      {
        at: 750,
        node: (
          <div className={styles.results}>
            <span data-hit="">
              Trail Runner <b>₹2,799</b>
            </span>
            <span>
              Aero Racer <b>₹6,299</b>
            </span>
          </div>
        ),
      },
    ],
    laneCaptions: [
      { at: 0, time: "0:00", caption: "Gets the question." },
      { at: 400, time: "0:01", caption: "Calls search_products(“running”)." },
    ],
    laneEnd: 1100,
    laneSeconds: 1,
    laneResult:
      "“The Trail Runner, at ₹2,799. The other running shoe is the Aero Racer, at ₹6,299.”",
    laneSteps: 1,
  },
  {
    id: "returns",
    label: "Return policy",
    question: "Can I return shoes I’ve worn once?",
    url: "northstar.example/policies",
    scene: "policy",
    original: [
      {
        at: 0,
        time: "0:01",
        caption: "Opens the store and looks for a returns link.",
        shot: true,
        cursor: [50, 50],
      },
      {
        at: 700,
        time: "0:05",
        caption: "A “10% off” pop-up covers the page.",
        shot: true,
        cursor: [84, 27],
        set: { popup: true },
      },
      {
        at: 1300,
        time: "0:09",
        caption: "Closes it and finds “Policies” in the footer.",
        cursor: [24, 88],
        set: { popup: false, footer: true },
      },
      {
        at: 1900,
        time: "0:14",
        caption: "The policy page is blank: its text loads with JavaScript.",
        shot: true,
        cursor: [50, 40],
      },
      {
        at: 2600,
        time: "0:21",
        caption: "Waits, scrolls, takes another screenshot.",
        shot: true,
        set: { loaded: true },
      },
      {
        at: 3200,
        time: "0:28",
        caption: "Reads “30 days” and stops there.",
        cursor: [40, 46],
        set: { read: true },
      },
    ],
    originalEnd: 3800,
    originalSeconds: 31,
    originalResult: {
      label: "Incomplete.",
      text: "“Yes, returns are accepted within 30 days.” Only unworn shoes qualify.",
    },
    shots: 4,
    lane: [
      {
        at: 400,
        node: <p className={styles.call}>GET /index.md · Policies</p>,
      },
      {
        at: 750,
        node: (
          <p className={styles.card}>
            <BookOpen size={14} /> Returns: unworn shoes, within 30 days,
            original box
          </p>
        ),
      },
    ],
    laneCaptions: [
      { at: 0, time: "0:00", caption: "Gets the question." },
      { at: 400, time: "0:01", caption: "Reads the store’s policies." },
    ],
    laneEnd: 1100,
    laneSeconds: 1,
    laneResult:
      "“No. Only unworn shoes can be returned, within 30 days and in the original box.”",
    laneSteps: 1,
  },
];

// What the browser agent is "thinking" at each beat, shown in a bubble by the cursor.
const THOUGHTS: Record<string, string[]> = {
  stock: [
    "Blank page…",
    "There it is.",
    "A pop-up?",
    "Where are the sizes?",
    "Which one is UK 9?",
    "Did that work?",
    "Log in? Stuck.",
  ],
  cheapest: [
    "Nothing here yet…",
    "Which are for running?",
    "A pop-up?",
    "Opening products…",
    "Still comparing…",
    "This one’s cheapest?",
  ],
  returns: [
    "Where are returns?",
    "A pop-up?",
    "Policies, maybe?",
    "Blank again…",
    "Waiting…",
    "30 days. Done?",
  ],
};
const TYPE_MS = 14; // per character of the lane's typed answer
const COUNT_MS = 700; // scoreboard count-up

function latest<T extends { at: number }>(items: T[], now: number) {
  return [...items].reverse().find((item) => now >= item.at) ?? items[0];
}

function sceneState(beats: Beat[], now: number): SceneState {
  return Object.assign(
    {},
    ...beats.filter((beat) => now >= beat.at).map((beat) => beat.set ?? {}),
  );
}

function clock(now: number, end: number, seconds: number) {
  const value = Math.round(Math.min(1, now / end) * seconds);
  return `0:${String(value).padStart(2, "0")}`;
}

function runLength(task: Task) {
  return Math.max(
    task.originalEnd + COUNT_MS + 100,
    task.laneEnd + task.laneResult.length * TYPE_MS + 100,
  );
}

function count(value: number, progress: number) {
  return Math.round(value * progress);
}

/** The mock page the browser agent sees, one per kind of task. */
function Scene({ task, state }: { task: Task; state: SceneState }) {
  if (task.scene === "listing")
    return (
      <div className={styles.listing} data-loaded={state.loaded || undefined}>
        {LISTING.map(([name, price], i) => (
          <span
            key={name}
            data-opened={(state.opened && [0, 3, 5].includes(i)) || undefined}
            data-picked={(state.picked && i === 1) || undefined}
          >
            <i />
            <em>{state.loaded ? name : ""}</em>
            <small>{state.loaded ? price : ""}</small>
          </span>
        ))}
      </div>
    );
  if (task.scene === "policy")
    return (
      <div className={styles.policy} data-loaded={state.loaded || undefined}>
        <i className={styles.lineLong} />
        {[86, 92, 70, 88, 60].map((width, i) => (
          <i
            key={i}
            className={styles.textLine}
            style={{ width: `${width}%` }}
            data-read={(state.read && i === 1) || undefined}
          />
        ))}
        <div
          className={styles.footerLinks}
          data-found={state.footer || undefined}
        >
          <span>About</span>
          <span>Policies</span>
          <span>Contact</span>
        </div>
      </div>
    );
  return (
    <>
      <div className={styles.page} data-loaded={state.loaded || undefined}>
        <i className={styles.photo} />
        <div>
          <i className={styles.lineLong} />
          <i className={styles.lineShort} />
          <div className={styles.sizes}>
            {SIZES.map((size, i) => (
              <span
                key={size}
                data-picked={(i === 2 && state.picked) || undefined}
              >
                <i />
                <b data-shown={state.question || undefined}>?</b>
              </span>
            ))}
          </div>
        </div>
      </div>
      <div
        className={styles.delivery}
        data-blocked={state.blocked || undefined}
      >
        <span>Check delivery</span>
        <strong>Log in required</strong>
      </div>
    </>
  );
}

/** One task replayed on the site as it is and on the agent lane. The visitor picks
 * the task; it plays once in view, and reduced motion shows the finished state. */
export function AgentRace() {
  const ref = useRef<HTMLElement>(null);
  const [taskIndex, setTaskIndex] = useState(0);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const frame = useRef(0);
  const reduced = useRef(false);
  const task = TASKS[taskIndex];

  const play = (length: number) => {
    cancelAnimationFrame(frame.current);
    if (reduced.current) {
      setElapsed(length);
      return;
    }
    // Time from the animation frames themselves: no clock reads while rendering.
    let begin: number | null = null;
    const tick = (time: number) => {
      begin ??= time;
      const now = time - begin;
      setElapsed(now);
      if (now < length) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
  };

  const choose = (index: number) => {
    setTaskIndex(index);
    play(runLength(TASKS[index]));
  };

  useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === "undefined") return;
    reduced.current = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (reduced.current) {
          setElapsed(runLength(TASKS[0]));
          observer.disconnect();
        } else if (entry.isIntersecting) {
          play(runLength(TASKS[0]));
          observer.disconnect();
        } else {
          setElapsed(0); // armed: starts when it scrolls into view
        }
      },
      { rootMargin: "0px 0px -20% 0px" },
    );
    observer.observe(node);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame.current);
    };
  }, []);

  const now = elapsed ?? runLength(task);
  const state = sceneState(task.original, now);
  const cursor = latest(
    task.original.filter((beat) => beat.cursor),
    now,
  ).cursor ?? [50, 50];
  const shots = task.original.filter(
    (beat) => beat.shot && now >= beat.at,
  ).length;
  const steps = task.original.filter((beat) => now >= beat.at).length;
  const left = latest(task.original, now);
  const right = latest(task.laneCaptions, now);
  const laneDone = now >= task.laneEnd;
  const originalDone = now >= task.originalEnd;
  const originalClock = Math.round(
    Math.min(1, now / task.originalEnd) * task.originalSeconds,
  );
  const waiting = Math.max(0, originalClock - task.laneSeconds);
  const beatIndex = task.original.indexOf(left);
  const thought = THOUGHTS[task.id]?.[beatIndex] ?? "";
  // A click ripple once the cursor has reached its target (0.45 s after the beat).
  const clickBeat = [...task.original]
    .reverse()
    .find(
      (beat) => beat.cursor && now >= beat.at + 450 && now < beat.at + 1100,
    );
  const typed = laneDone
    ? task.laneResult.slice(0, Math.floor((now - task.laneEnd) / TYPE_MS))
    : "";
  const typing = laneDone && typed.length < task.laneResult.length;
  const tally = originalDone
    ? Math.min(1, (now - task.originalEnd) / COUNT_MS)
    : 0;

  return (
    <section
      ref={ref}
      id="demo"
      className={styles.section}
      aria-labelledby="race-title"
    >
      <div className={styles.wrap}>
        <p className={styles.label}>Demo</p>
        <h2 id="race-title" className={styles.title}>
          One request. Two very different trips.
        </h2>
        <div className={styles.task}>
          <div className={styles.tasks} role="group" aria-label="Choose a task">
            {TASKS.map((item, index) => (
              <button
                key={item.id}
                type="button"
                aria-pressed={index === taskIndex}
                onClick={() => choose(index)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            className={styles.replay}
            onClick={() => play(runLength(task))}
            aria-label="Replay the demo"
          >
            <RotateCcw size={14} aria-hidden="true" /> Replay
          </button>
          <p className={styles.question}>
            <span className={styles.taskTag}>Task</span>“{task.question}”
          </p>
        </div>

        {/* The full story for screen readers; the scenes below are visual only. */}
        <div className="sr-only">
          <p>On the site as it is:</p>
          <ol>
            {task.original.map((beat) => (
              <li key={beat.at}>
                {beat.time} {beat.caption}
              </li>
            ))}
          </ol>
          <p>
            On the agent lane, the answer comes back in{" "}
            {task.laneSeconds === 1
              ? "one second"
              : `${task.laneSeconds} seconds`}
            .
          </p>
        </div>

        <div className={styles.lanes}>
          <article className={styles.original}>
            <header>
              <strong>Your site today</strong>
              <span aria-hidden="true">
                {clock(now, task.originalEnd, task.originalSeconds)} · {steps}{" "}
                {steps === 1 ? "step" : "steps"}
              </span>
              <i className={styles.progress} aria-hidden="true">
                <b
                  style={{
                    transform: `scaleX(${Math.min(1, now / task.originalEnd)})`,
                  }}
                />
              </i>
            </header>
            <div className={styles.stage} aria-hidden="true">
              <div className={styles.urlBar}>{task.url}</div>
              <Scene task={task} state={state} />
              <i className={styles.dim} data-shown={state.popup || undefined} />
              <div
                className={styles.popup}
                data-shown={state.popup || undefined}
              >
                10% off your first order <span>×</span>
              </div>
              {shots > 0 && (
                <i key={`${task.id}-${shots}`} className={styles.flash} />
              )}
              <span className={styles.shots}>
                {shots} {shots === 1 ? "screenshot" : "screenshots"}
              </span>
              <svg
                className={styles.cursor}
                style={{ left: `${cursor[0]}%`, top: `${cursor[1]}%` }}
                viewBox="0 0 24 24"
              >
                <path d="M4 2l14 9-6 1.5L9 19z" />
              </svg>
              {clickBeat?.cursor && (
                <i
                  key={`${task.id}-click-${clickBeat.at}`}
                  className={styles.ripple}
                  style={{
                    left: `${clickBeat.cursor[0]}%`,
                    top: `${clickBeat.cursor[1]}%`,
                  }}
                />
              )}
              {thought && !originalDone && (
                <span
                  key={`${task.id}-think-${beatIndex}`}
                  className={styles.thought}
                  data-flip={cursor[0] > 60 || undefined}
                  style={{ left: `${cursor[0]}%`, top: `${cursor[1]}%` }}
                >
                  {thought}
                </span>
              )}
            </div>
            <p className={styles.caption} aria-hidden="true">
              <span>{left.time}</span> {left.caption}
            </p>
            <p className={styles.result} data-shown={originalDone || undefined}>
              <strong>{task.originalResult.label}</strong>{" "}
              {task.originalResult.text}
            </p>
          </article>

          <article className={styles.lane}>
            <header>
              <strong>With the agent lane</strong>
              <span aria-hidden="true">
                {clock(now, task.laneEnd, task.laneSeconds)}
                {laneDone
                  ? originalDone
                    ? " · done"
                    : ` · done, waiting +${waiting}s`
                  : ""}
              </span>
              <i className={styles.progress} aria-hidden="true">
                <b
                  style={{
                    transform: `scaleX(${Math.min(1, now / task.laneEnd)})`,
                  }}
                />
              </i>
            </header>
            <div
              className={styles.chat}
              aria-hidden="true"
              data-running={(now > 0 && !laneDone) || undefined}
            >
              <p className={styles.ask} data-shown={now >= 150 || undefined}>
                {task.question}
              </p>
              {task.lane.map((item) => (
                <div key={item.at} data-shown={now >= item.at || undefined}>
                  {item.node}
                </div>
              ))}
            </div>
            <p className={styles.caption} aria-hidden="true">
              <span>{right.time}</span> {laneDone ? "Answered." : right.caption}
            </p>
            <p className={styles.result} data-shown={laneDone || undefined}>
              <strong>Done.</strong>{" "}
              <span className="sr-only">{task.laneResult}</span>
              <span aria-hidden="true">
                {laneDone ? typed : task.laneResult}
                {typing && <i className={styles.caret} />}
              </span>
            </p>
          </article>
        </div>

        <div className={styles.score} data-shown={originalDone || undefined}>
          <p className={styles.scoreHead}>
            <span>For this task</span>
            <span>Your site today</span>
            <span>Agent lane</span>
          </p>
          <p>
            <span>Time to answer</span>
            <span>{count(task.originalSeconds, tally)} s</span>
            <span>{count(task.laneSeconds, tally)} s</span>
          </p>
          <p>
            <span>Steps</span>
            <span>{count(task.original.length, tally)}</span>
            <span>{count(task.laneSteps, tally)}</span>
          </p>
          <p>
            <span>Screenshots</span>
            <span>{count(task.shots, tally)}</span>
            <span>0</span>
          </p>
          <p>
            <span>Answer</span>
            <span data-tone="bad">
              {task.originalResult.label.slice(0, -1)}
            </span>
            <span data-tone="good" data-pop={tally >= 1 || undefined}>
              Correct
            </span>
          </p>
        </div>
        <p className={styles.note}>
          Pick a task to replay it. The agent-lane answers are our demo store’s
          real ones; the other side is an illustrative replay of the store’s
          real problems, to be replaced by measured runs from our agent tests.
        </p>
      </div>
    </section>
  );
}
