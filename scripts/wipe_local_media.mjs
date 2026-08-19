/**
 * Wipe project media on this PC. Does not touch MongoDB / Atlas / GridFS.
 *
 * Usage (repo root):  npm run wipe
 * Dry run:            npm run wipe -- --dry-run
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, "..");
const DRY = process.argv.includes("--dry-run");

const MEDIA_EXT = new Set([
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".gif",
  ".mp4",
  ".webm",
  ".mov",
  ".avi",
  ".mkv",
  ".bmp",
]);

const DEFAULT_COMFY =
  "E:\\Comfy-Desktop\\ComfyUI-Installs\\Khelukhiladi\\ComfyUI";

function readEnv(key) {
  const envPath = path.join(REPO, ".env");
  if (!fs.existsSync(envPath)) return "";
  const text = fs.readFileSync(envPath, "utf8");
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const i = line.indexOf("=");
    if (i < 1) continue;
    if (line.slice(0, i).trim() === key) {
      return line.slice(i + 1).trim().replace(/^["']|["']$/g, "");
    }
  }
  return "";
}

const stats = { files: 0, dirs: 0, skipped: 0, errors: 0 };

function log(msg) {
  console.log(msg);
}

function unlinkFile(file) {
  try {
    if (DRY) {
      log(`  dry  ${file}`);
    } else {
      try {
        fs.chmodSync(file, 0o666);
      } catch {
        /* ignore */
      }
      fs.unlinkSync(file);
      log(`  del  ${file}`);
    }
    stats.files += 1;
  } catch (err) {
    stats.errors += 1;
    log(`  err  ${file}  (${err.message})`);
  }
}

function rmdirIfEmpty(dir) {
  try {
    if (!fs.existsSync(dir)) return;
    const left = fs.readdirSync(dir);
    if (left.length) return;
    if (!DRY) fs.rmdirSync(dir);
    stats.dirs += 1;
  } catch {
    /* keep parent folders Comfy expects */
  }
}

function walkFiles(root) {
  const out = [];
  if (!fs.existsSync(root)) return out;
  const stack = [root];
  while (stack.length) {
    const cur = stack.pop();
    let entries;
    try {
      entries = fs.readdirSync(cur, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const e of entries) {
      const full = path.join(cur, e.name);
      if (e.isDirectory()) stack.push(full);
      else if (e.isFile()) out.push(full);
    }
  }
  return out;
}

function wipeTree(root, { keepRoot = true, filter = null } = {}) {
  if (!fs.existsSync(root)) {
    stats.skipped += 1;
    log(`skip  ${root}  (missing)`);
    return;
  }
  log(`${DRY ? "scan" : "wipe"} ${root}`);
  const files = walkFiles(root);
  const dirs = [];
  for (const file of files) {
    if (filter && !filter(file)) continue;
    unlinkFile(file);
    dirs.push(path.dirname(file));
  }
  const uniqueDirs = [...new Set(dirs)].sort(
    (a, b) => b.length - a.length || b.localeCompare(a),
  );
  for (const dir of uniqueDirs) {
    if (path.resolve(dir) === path.resolve(root) && keepRoot) continue;
    rmdirIfEmpty(dir);
  }
  if (!keepRoot && fs.existsSync(root)) {
    try {
      if (!DRY) fs.rmSync(root, { recursive: true, force: true });
      stats.dirs += 1;
      log(`  rmdir ${root}`);
    } catch (err) {
      stats.errors += 1;
      log(`  err  ${root}  (${err.message})`);
    }
  }
}

function isMedia(file) {
  return MEDIA_EXT.has(path.extname(file).toLowerCase());
}

function isTrainDump(file) {
  const name = path.basename(file).toLowerCase();
  if (isMedia(file)) return true;
  if (name.startsWith("job_") && name.endsWith(".json")) return true;
  if (name === "last_job.json") return true;
  return false;
}

function isWanDownload(file) {
  const name = path.basename(file);
  if (!isMedia(file)) return false;
  return /^wan_(img|vid|out)_/i.test(name);
}

const comfyDir = readEnv("COMFYUI_DIR") || DEFAULT_COMFY;

log(DRY ? "Local media wipe (dry run) — Mongo/Atlas not touched" : "Local media wipe — Mongo/Atlas not touched");
log("");

wipeTree(path.join(REPO, "tmp_test", "train"), { filter: isTrainDump });
wipeTree(path.join(REPO, "tmp_test", "review"), { keepRoot: false });

for (const folder of ["outputs", "temp", "tmp", "temptest_assets"]) {
  wipeTree(path.join(REPO, folder), { keepRoot: false });
}

for (const side of ["input", "output", "temp"]) {
  wipeTree(path.join(comfyDir, side), { keepRoot: true });
}

const tempRoot = os.tmpdir();
if (fs.existsSync(tempRoot)) {
  let thumbDirs = [];
  try {
    thumbDirs = fs
      .readdirSync(tempRoot, { withFileTypes: true })
      .filter((e) => e.isDirectory() && e.name.startsWith("wan_thumb_"))
      .map((e) => path.join(tempRoot, e.name));
  } catch {
    thumbDirs = [];
  }
  if (!thumbDirs.length) {
    stats.skipped += 1;
    log(`skip  ${path.join(tempRoot, "wan_thumb_*")}  (none)`);
  } else {
    for (const dir of thumbDirs) {
      wipeTree(dir, { keepRoot: false });
    }
  }
}

const downloads = path.join(os.homedir(), "Downloads");
wipeTree(downloads, { keepRoot: true, filter: isWanDownload });

log("");
log(
  `${DRY ? "Would remove" : "Removed"} ${stats.files} file(s), ${stats.dirs} dir(s). skipped=${stats.skipped} errors=${stats.errors}`,
);
log("MongoDB Atlas / GridFS was not modified.");
if (stats.errors) process.exit(1);
