const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const rootDir = path.resolve(__dirname, '..');
const pfxPath = path.join(rootDir, 'CabinetCRM.pfx');
const pfxPassword = 'testpassword';

// 1. Rechercher signtool.exe
function findSignTool() {
  const possiblePaths = [
    'C:\\Program Files (x86)\\Windows Kits\\10\\bin\\10.0.26100.0\\x64\\signtool.exe',
    'C:\\Program Files (x86)\\Windows Kits\\10\\App Certification Kit\\signtool.exe',
  ];
  
  // Essayer de le trouver de manière dynamique dans le dossier Windows Kits s'il y a d'autres versions
  try {
    const parentDir = 'C:\\Program Files (x86)\\Windows Kits\\10\\bin';
    if (fs.existsSync(parentDir)) {
      const subdirs = fs.readdirSync(parentDir);
      for (const dir of subdirs) {
        const p = path.join(parentDir, dir, 'x64', 'signtool.exe');
        if (fs.existsSync(p)) {
          possiblePaths.unshift(p);
        }
      }
    }
  } catch (e) {}

  for (const p of possiblePaths) {
    if (fs.existsSync(p)) {
      return p;
    }
  }
  return null;
}

// 2. Générer et importer le certificat si nécessaire
function ensureCertificate() {
  if (fs.existsSync(pfxPath)) {
    return;
  }
  
  console.log("Génération du certificat d'auto-signature CabinetCRM...");
  try {
    const psCommands = [
      `$cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=CabinetCRM' -FriendlyName 'CabinetCRM' -CertStoreLocation 'Cert:\\CurrentUser\\My'`,
      `$pwd = ConvertTo-SecureString '${pfxPassword}' -AsPlainText -Force`,
      `Export-PfxCertificate -Cert $cert -FilePath '${pfxPath}' -Password $pwd`,
      `Import-PfxCertificate -FilePath '${pfxPath}' -CertStoreLocation 'Cert:\\CurrentUser\\Root' -Password $pwd`
    ];
    const psCommand = psCommands.join('; ');

    execSync(`powershell -Command "${psCommand}"`, { stdio: 'inherit' });
    console.log("Certificat d'auto-signature généré et installé avec succès dans CurrentUser\\Root.");
  } catch (e) {
    console.error("Échec de la génération du certificat :", e.message);
  }
}

function run() {
  const signtool = findSignTool();
  if (!signtool) {
    console.warn("Avertissement : signtool.exe introuvable sur le système. L'installateur ne sera pas signé.");
    return;
  }

  ensureCertificate();

  if (!fs.existsSync(pfxPath)) {
    console.warn("Avertissement : Certificat PFX de test introuvable. Signature annulée.");
    return;
  }

  // 3. Lire la version de tauri.conf.json pour trouver l'installateur
  const tauriConfPath = path.join(rootDir, 'apps', 'web', 'src-tauri', 'tauri.conf.json');
  if (!fs.existsSync(tauriConfPath)) {
    console.error("Fichier tauri.conf.json introuvable !");
    return;
  }

  const tauriConf = JSON.parse(fs.readFileSync(tauriConfPath, 'utf8'));
  const version = tauriConf.version; // ex: "1.0.0-56"

  const installerPath = path.join(
    rootDir,
    'apps',
    'web',
    'src-tauri',
    'target',
    'release',
    'bundle',
    'nsis',
    `Cabinet CRM_${version}_x64-setup.exe`
  );

  if (!fs.existsSync(installerPath)) {
    console.error(`Installateur introuvable à : ${installerPath}`);
    return;
  }

  // 4. Signer l'installateur
  console.log(`Signature de l'installateur : ${installerPath}`);
  try {
    const signCmd = `"${signtool}" sign /f "${pfxPath}" /p "${pfxPassword}" /fd sha256 /td sha256 /tr http://timestamp.digicert.com "${installerPath}"`;
    execSync(signCmd, { stdio: 'inherit' });
    console.log("Installateur signé numériquement avec succès !");
  } catch (e) {
    console.error("Échec de la signature de l'installateur :", e.message);
  }
}

run();
