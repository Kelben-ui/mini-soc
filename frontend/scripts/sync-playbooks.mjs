// Copy the canonical playbooks from the repository's playbooks/ directory into
// frontend/public/playbooks/ so Vite serves exactly one authored copy.
//
// The playbooks are written once under playbooks/ (reviewed, linked from the
// docs) and copied here at dev/build time. This keeps a single source of truth
// and means the served copy can never drift from the documented one.
//
// Wired into npm scripts as predev and prebuild (see package.json).
import {
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
  rmSync,
} from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const source = resolve(here, '../../playbooks');
const dest = resolve(here, '../public/playbooks');

if (!existsSync(source)) {
  console.error(`sync-playbooks: source directory not found: ${source}`);
  process.exit(1);
}

rmSync(dest, { recursive: true, force: true });
mkdirSync(dest, { recursive: true });

const copied = [];
for (const name of readdirSync(source)) {
  if (!name.endsWith('.md') || name.toLowerCase() === 'readme.md') continue;
  cpSync(join(source, name), join(dest, name));
  copied.push(name);
}

if (copied.length === 0) {
  console.error(`sync-playbooks: no playbooks found in ${source}`);
  process.exit(1);
}

console.log(`sync-playbooks: copied ${copied.join(', ')} -> public/playbooks/`);
