const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const rootDir = path.resolve(__dirname, '..');

function getGitInfo() {
  try {
    const commitCount = execSync('git rev-list --count HEAD', { encoding: 'utf8', cwd: rootDir }).trim();
    const commitHash = execSync('git rev-parse --short HEAD', { encoding: 'utf8', cwd: rootDir }).trim();
    return { commitCount: parseInt(commitCount, 10), commitHash };
  } catch (e) {
    console.warn("Impossible d'obtenir les infos Git, utilisation des valeurs par défaut :", e.message);
    return { commitCount: 0, commitHash: 'unknown' };
  }
}

function run() {
  const { commitCount, commitHash } = getGitInfo();
  const timestamp = new Date().toISOString().replace(/T/, ' ').replace(/\..+/, '').slice(0, 16); // YYYY-MM-DD HH:MM

  // 1. Lire la version de base depuis apps/web/package.json
  const webPkgPath = path.join(rootDir, 'apps', 'web', 'package.json');
  const webPkg = JSON.parse(fs.readFileSync(webPkgPath, 'utf8'));
  const baseVersion = webPkg.version || '1.0.0';

  // S'assurer que le format est major.minor.patch
  const versionParts = baseVersion.split('.');
  const major = versionParts[0] || '1';
  const minor = versionParts[1] || '0';
  const patch = versionParts[2] || '0';

  const fullVersion = `${major}.${minor}.${patch}-${commitCount}`;
  console.log(`Génération des infos de build : Base=${baseVersion}, CommitCount=${commitCount}, VersionFinale=${fullVersion}`);

  // 2. Mettre à jour tauri.conf.json
  const tauriConfPath = path.join(rootDir, 'apps', 'web', 'src-tauri', 'tauri.conf.json');
  if (fs.existsSync(tauriConfPath)) {
    const tauriConf = JSON.parse(fs.readFileSync(tauriConfPath, 'utf8'));
    tauriConf.version = fullVersion;
    fs.writeFileSync(tauriConfPath, JSON.stringify(tauriConf, null, 2), 'utf8');
    console.log(`tauri.conf.json mis à jour avec la version : ${fullVersion}`);
  } else {
    console.warn("Fichier tauri.conf.json introuvable !");
  }

  // 3. Écrire crm/_build_info.py pour le backend Python
  const buildInfoPyPath = path.join(rootDir, 'apps', 'api', 'crm', '_build_info.py');
  const buildInfoPyContent = `# Ce fichier est généré automatiquement lors du build. Ne pas modifier.
VERSION = "${major}.${minor}.${patch}"
BUILD = "${commitCount}"
COMMIT = "${commitHash}"
TIMESTAMP = "${timestamp}"
`;
  fs.writeFileSync(buildInfoPyPath, buildInfoPyContent, 'utf8');
  console.log(`crm/_build_info.py généré à ${buildInfoPyPath}`);
}

run();
