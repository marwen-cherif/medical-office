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
  const exeName = process.platform === 'win32' ? 'crm-server.exe' : 'crm-server';
  const srcPath = path.join(srcDir, exeName);

  const destDir = path.join(__dirname, '..', '..', 'web', 'src-tauri', 'binaries');
  const destPath = path.join(destDir, `crm-server-${triple}.exe`);

  if (!fs.existsSync(srcPath)) {
    console.error(`Source binary not found at ${srcPath}. Did pyinstaller build fail?`);
    process.exit(1);
  }

  if (!fs.existsSync(destDir)) {
    fs.mkdirSync(destDir, { recursive: true });
  }

  fs.copyFileSync(srcPath, destPath);
  console.log(`Successfully copied sidecar to ${destPath}`);
} catch (err) {
  console.error('Error copying sidecar:', err);
  process.exit(1);
}
