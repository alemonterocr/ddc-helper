// Rasterizes public/favicon.svg to PNG at the sizes Chrome's manifest expects.
// Runs on `npm run build` (see package.json). Idempotent: skips regeneration
// when every output PNG is newer than the source SVG.
//
// Output paths match the manifest's `icons` and `action.default_icon` entries.

import { statSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import sharp from "sharp";

const HERE = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(HERE, "..");
const PUBLIC_DIR = resolve(PROJECT_ROOT, "public");
const SOURCE_SVG = resolve(PUBLIC_DIR, "favicon.svg");
const SIZES = [16, 32, 48, 128];

function outputPath(size) {
  return resolve(PUBLIC_DIR, `icon-${size}.png`);
}

function upToDate() {
  if (!existsSync(SOURCE_SVG)) return false;
  const svgMtime = statSync(SOURCE_SVG).mtimeMs;
  return SIZES.every((size) => {
    const out = outputPath(size);
    return existsSync(out) && statSync(out).mtimeMs >= svgMtime;
  });
}

async function main() {
  if (!existsSync(SOURCE_SVG)) {
    console.error(`[icons] Source SVG not found: ${SOURCE_SVG}`);
    process.exit(1);
  }

  if (upToDate()) {
    console.log("[icons] PNGs up to date, skipping.");
    return;
  }

  const started = Date.now();
  await Promise.all(
    SIZES.map(async (size) => {
      await sharp(SOURCE_SVG)
        .resize(size, size, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
        .png({ compressionLevel: 9 })
        .toFile(outputPath(size));
    }),
  );
  console.log(
    `[icons] Rasterized ${SIZES.length} PNGs (${SIZES.join(", ")}) in ${Date.now() - started}ms`,
  );
}

main().catch((err) => {
  console.error("[icons] Failed to generate icons:", err);
  process.exit(1);
});
