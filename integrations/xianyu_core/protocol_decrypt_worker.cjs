const fs = require("fs");
const readline = require("readline");

const sourcePath = process.argv[2];
if (!sourcePath) {
  process.stderr.write("missing protocol source path\n");
  process.exit(2);
}

const source = fs.readFileSync(sourcePath, "utf8");
const createDecrypt = new Function("require", `${source}\nreturn decrypt;`);
const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });

input.on("line", (line) => {
  let request;
  try {
    request = JSON.parse(line);
    // The upstream decoder mutates bundle-level parsing state. A fresh closure
    // per job keeps one malformed or complex payload from poisoning later jobs.
    const decrypt = createDecrypt(require);
    const result = decrypt(String(request.data || ""));
    process.stdout.write(`${JSON.stringify({ id: request.id, result })}\n`);
  } catch (error) {
    process.stdout.write(
      `${JSON.stringify({
        id: request && request.id,
        error: error instanceof Error ? error.message : String(error)
      })}\n`
    );
  }
});
