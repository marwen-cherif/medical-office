const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

try {
  let triple = 'x86_64-pc-windows-msvc';
  try {
    const rustcInfo = execSync('rustc -Vv').toString();
    const match = rustcInfo.match(/^host:\s+(\S+)/m);
    if (match) {
      triple = match[1];
    }
  } catch (e) {
    console.warn('Could not detect rustc target triple, defaulting to x86_64-pc-windows-msvc');
  }

  const srcDir = path.join(__dirname, '..', 'dist');
  const destDir = path.join(__dirname, '..', '..', 'web', 'src-tauri', 'binaries');

  if (!fs.existsSync(destDir)) {
    fs.mkdirSync(destDir, { recursive: true });
  }

  // Binaires externes à copier dans src-tauri/binaries/ :
  //  - crm-server : sidecar FastAPI (console=True, handshake stdout pour Tauri).
  //  - crm-tray   : worker de fond windowed (console=False) pour les rappels.
  const isWin = process.platform === 'win32';
  const binaries = ['crm-server', 'crm-tray'];

  for (const base of binaries) {
    const exeName = isWin ? `${base}.exe` : base;
    const srcPath = path.join(srcDir, exeName);
    const destExe = isWin ? `${base}-${triple}.exe` : `${base}-${triple}`;
    const destPath = path.join(destDir, destExe);

    if (!fs.existsSync(srcPath)) {
      console.error(`Source binary not found at ${srcPath}. Did pyinstaller build fail?`);
      process.exit(1);
    }

    fs.copyFileSync(srcPath, destPath);
    console.log(`Successfully copied ${base} to ${destPath}`);
  }

  // Copier le template config.default.ini
  const configSrc = path.join(__dirname, '..', 'config.default.ini');
  const resourcesDestDir = path.join(__dirname, '..', '..', 'web', 'src-tauri', 'resources');
  if (!fs.existsSync(resourcesDestDir)) {
    fs.mkdirSync(resourcesDestDir, { recursive: true });
  }
  const configDest = path.join(resourcesDestDir, 'config.default.ini');
  if (fs.existsSync(configSrc)) {
    fs.copyFileSync(configSrc, configDest);
    console.log(`Successfully copied config.default.ini to ${configDest}`);
  } else {
    console.error(`Source config.default.ini not found at ${configSrc}`);
    process.exit(1);
  }
} catch (err) {
  console.error('Error copying sidecar:', err);
  process.exit(1);
}
