/**
 * Hash a PIN with bcryptjs (cost 12). Print only the hash.
 *
 *   node frontend/scripts/hash_pin.js <pin>
 *   npm run hash-pin -- <pin>   (from frontend/)
 */
import bcrypt from "bcryptjs";

const pin = String(process.argv[2] || "").trim();
if (!pin) {
  console.error("usage: node scripts/hash_pin.js <pin>");
  process.exit(1);
}

process.stdout.write(bcrypt.hashSync(pin, 12));
