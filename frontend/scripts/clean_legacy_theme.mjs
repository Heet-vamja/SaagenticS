// Remove unreachable legacy landing CSS, preserving dynamically named status classes.
import fs from "node:fs";
import path from "node:path";
import postcss from "postcss";
function files(dir) {
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .flatMap((e) =>
      e.isDirectory()
        ? files(path.join(dir, e.name))
        : [path.join(dir, e.name)],
    );
}
const source = files("src")
  .filter((f) => /\.(tsx|ts)$/.test(f))
  .map((f) => fs.readFileSync(f, "utf8"))
  .join("\n");
const filename = "src/app/globals.css";
const root = postcss.parse(fs.readFileSync(filename, "utf8"));
let removed = 0;
root.walkRules((rule) => {
  if (rule.selector.includes("\\")) return;
  if (
    /\.(entry-[\w-]+|website-entry|hero-title-row|hero-title-can|hero-provider-name)(?![\w-])/.test(
      rule.selector,
    )
  ) {
    rule.remove();
    removed++;
    return;
  }
  const selectors = rule.selectors.filter((selector) => {
    const names = [...selector.matchAll(/\.([_a-zA-Z][\w-]*)/g)].map(
      (match) => match[1],
    );
    return names.every(
      (name) =>
        name.startsWith("status-") ||
        new RegExp("(?<![\\w-])" + name + "(?![\\w-])").test(source),
    );
  });
  if (!selectors.length) {
    rule.remove();
    removed++;
  } else rule.selectors = selectors;
});
root.walkAtRules((rule) => {
  if (rule.nodes && !rule.nodes.length) rule.remove();
});
fs.writeFileSync(filename, root.toString());
process.stdout.write(`Removed ${removed} unreachable legacy CSS rules.\n`);
