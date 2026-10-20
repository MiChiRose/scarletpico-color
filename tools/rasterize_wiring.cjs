// Optional PNG export for GitHub; npm install --no-save sharp in a tool env.
// SHARP_MODULE may point to an already-installed module, without vendoring it.
const path = require('node:path');
const sharp = require(process.env.SHARP_MODULE || 'sharp');
const assets = path.resolve(__dirname, '../docs/assets');
(async () => {
  for (const name of ['wiring-signals', 'wiring-power']) {
    await sharp(path.join(assets, name + '.svg')).png().toFile(path.join(assets, name + '.png'));
    console.log(name + '.png');
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
