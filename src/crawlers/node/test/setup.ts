import fs from "fs";
import path from "path";

export const mochaHooks = {
  afterAll() {
    const cwd = fs.realpathSync(process.cwd());
    const entries = fs.readdirSync(cwd, { withFileTypes: true });
    const patterns = [/^tmp-[A-Za-z0-9]/, /^tmp-e2e-[A-Za-z0-9]/, /^tmp-smoke-[A-Za-z0-9]/];

    for (const ent of entries) {
      if (!ent.isDirectory()) continue;
      const name = ent.name;
      if (!patterns.some((rx) => rx.test(name))) continue;
      const full = path.join(cwd, name);
      try {
        fs.rmSync(full, { recursive: true, force: true });
        // eslint-disable-next-line no-console
        console.log(`[cleanup] removed temp directory: ${name}`);
      } catch (e) {
        // eslint-disable-next-line no-console
        console.warn(`[cleanup] failed to remove ${name}:`, (e as any)?.message || e);
      }
    }
  },
};
