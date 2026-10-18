// منبع نمادها یک‌جاست؛ خروجی یکسان برای هر سه رابط و بستهٔ ویندوز ساخته می‌شود.
import { readFile, writeFile, mkdir, copyFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";

const home = dirname(fileURLToPath(import.meta.url));
const root = resolve(home, "../..");
const require = createRequire(join(root, ".codex/tools/brand/package.json"));
const { Resvg } = require("@resvg/resvg-js");
const icons = JSON.parse(await readFile(join(home, "icons.json"), "utf8"));
const mark = await readFile(join(home, "mark.svg"), "utf8");

function raster(size) {
  return new Resvg(mark, { fitTo: { mode: "width", value: size } }).render().asPng();
}

function windowsIcon() {
  const sizes = [16, 20, 24, 32, 48, 64, 128, 256];
  const header = Buffer.alloc(6 + sizes.length * 16);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(sizes.length, 4);
  const images = [];
  let offset = header.length;
  sizes.forEach((size, index) => {
    const data = raster(size);
    const entry = 6 + index * 16;
    header[entry] = size === 256 ? 0 : size;
    header[entry + 1] = size === 256 ? 0 : size;
    header.writeUInt16LE(1, entry + 4);
    header.writeUInt16LE(32, entry + 6);
    header.writeUInt32LE(data.length, entry + 8);
    header.writeUInt32LE(offset, entry + 12);
    images.push(data);
    offset += data.length;
  });
  return Buffer.concat([header, ...images]);
}

async function distribute(destination) {
  await mkdir(join(destination, "icons"), { recursive: true });
  await copyFile(join(home, "mark.svg"), join(destination, "mark.svg"));
  await writeFile(join(destination, "app-icon.png"), raster(192));
  let css = ".rasam-icon { display:inline-block; width:1.1em; height:1.1em; flex-shrink:0; vertical-align:-.15em; margin-inline-end:.4em; background-color:currentColor; -webkit-mask:var(--rasam-icon) center/contain no-repeat; mask:var(--rasam-icon) center/contain no-repeat; }\n";
  for (const [name, icon] of Object.entries(icons)) {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="${icon.path}" fill="none" stroke="#173d36" stroke-width="1.7" stroke-linecap="square" stroke-linejoin="miter"/></svg>\n`;
    await writeFile(join(destination, "icons", name + ".svg"), svg);
    css += `.icon-${name} { --rasam-icon:url("icons/${name}.svg"); }\n`;
  }
  await writeFile(join(destination, "brand.css"), css);
}

await writeFile(join(home, "rasam.ico"), windowsIcon());
await writeFile(join(home, "app-icon.png"), raster(512));
for (const directory of ["website/public", "admin_panel/public", "rasam/desktop/static"]) {
  await distribute(join(root, directory));
}
console.log(`نماد برنامه و ${Object.keys(icons).length} آیکون برای سه رابط ساخته شد.`);
