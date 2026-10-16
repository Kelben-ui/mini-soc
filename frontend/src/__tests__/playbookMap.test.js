import { readFileSync, readdirSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { PLAYBOOK_FALLBACK, PLAYBOOK_MAP, playbookFor } from "../playbookMap";

// frontend/src/__tests__ -> repo root is three levels up.
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const rulesDir = join(repoRoot, "rules");
const playbooksDir = join(repoRoot, "playbooks");

function ruleIds() {
  return readdirSync(rulesDir)
    .filter((name) => name.endsWith(".yaml"))
    .map((name) => {
      const text = readFileSync(join(rulesDir, name), "utf8");
      const match = text.match(/^id:\s*(\S+)/m);
      return match ? match[1] : null;
    })
    .filter(Boolean);
}

describe("playbookMap", () => {
  it("has an entry for every detection rule", () => {
    const ids = ruleIds();
    expect(ids.length).toBeGreaterThan(0);

    const missing = ids.filter((id) => !PLAYBOOK_MAP[id]);
    expect(missing).toEqual([]);
  });

  it("maps only to playbook files that exist in the repository", () => {
    for (const [ruleId, file] of Object.entries(PLAYBOOK_MAP)) {
      expect(file, `${ruleId} -> ${file}`).toMatch(/\.md$/);
      expect(
        existsSync(join(playbooksDir, file)),
        `${ruleId} -> playbooks/${file}`
      ).toBe(true);
    }
  });

  it("falls back to an existing umbrella playbook for unknown rules", () => {
    expect(existsSync(join(playbooksDir, PLAYBOOK_FALLBACK))).toBe(true);
    expect(playbookFor("NOT-A-RULE")).toBe(PLAYBOOK_FALLBACK);
  });

  it("resolves a mapped rule to its own playbook", () => {
    expect(playbookFor("SSH-BF-001")).toBe("ssh-brute-force.md");
  });
});
