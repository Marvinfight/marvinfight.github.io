import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const defaultRepositoryRoot = path.resolve(scriptDirectory, '..', '..');
const repositoryRoot = path.resolve(process.argv[2] ?? defaultRepositoryRoot);
const distDirectory = path.resolve(
  process.argv[3] ?? path.join(repositoryRoot, 'zysd', 'dist'),
);
const outputDirectory = path.resolve(
  process.argv[4] ?? path.join(repositoryRoot, '_site'),
);

const excludedRootEntries = new Set([
  '.git',
  '.github',
  '.superpowers',
  '_site',
  'zysd',
]);

if (!fs.existsSync(path.join(distDirectory, 'index.html'))) {
  throw new Error(`Missing calculator build at ${distDirectory}. Run the Vite build first.`);
}

fs.rmSync(outputDirectory, { recursive: true, force: true });
fs.mkdirSync(outputDirectory, { recursive: true });

for (const entry of fs.readdirSync(repositoryRoot, { withFileTypes: true })) {
  if (excludedRootEntries.has(entry.name)) continue;

  fs.cpSync(
    path.join(repositoryRoot, entry.name),
    path.join(outputDirectory, entry.name),
    { recursive: true, preserveTimestamps: true },
  );
}

fs.cpSync(distDirectory, path.join(outputDirectory, 'zysd'), {
  recursive: true,
  preserveTimestamps: true,
});
fs.writeFileSync(path.join(outputDirectory, '.nojekyll'), '', 'utf8');

