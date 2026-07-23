import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const [sourcePath, outputPath, sourceCommit = "unknown"] = process.argv.slice(2);

if (!sourcePath || !outputPath) {
  throw new Error(
    "usage: node tools/build_product_region_catalog.mjs <info.json> <output.json> [source-commit]"
  );
}

const source = JSON.parse(await readFile(resolve(sourcePath), "utf8"));
const regions = Object.values(source)
  .flatMap((item) => item.children ?? [])
  .map((item) => {
    if (!Array.isArray(item.center) || item.center.length !== 2) {
      throw new Error(`region ${item.adcode} is missing center coordinates`);
    }
    return [
      String(item.adcode),
      String(item.parent?.adcode ?? "100000"),
      item.name,
      item.level,
      Number(item.center[0]),
      Number(item.center[1])
    ];
  })
  .sort((left, right) => left[0].localeCompare(right[0]));

if (new Set(regions.map((item) => item[0])).size !== regions.length) {
  throw new Error("region catalog contains duplicate administrative codes");
}

const catalog = {
  source: "DataV.GeoAtlas via zhChuXiao/ChinaGeoJson",
  source_url: "https://github.com/zhChuXiao/ChinaGeoJson",
  source_commit: sourceCommit,
  levels: ["province", "city", "district"],
  items: regions
};

await writeFile(resolve(outputPath), `${JSON.stringify(catalog)}\n`, "utf8");
console.log(`wrote ${regions.length} regions to ${outputPath}`);
