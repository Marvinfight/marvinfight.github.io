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

const rootIndexFile = path.join(outputDirectory, 'index.html');
if (!fs.existsSync(rootIndexFile)) {
  fs.writeFileSync(
    rootIndexFile,
    `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta http-equiv="refresh" content="0; url=/zysd/" />
    <title>江苏电力曲线计算器</title>
    <style>
      :root { color-scheme: light; font-family: Inter, "Microsoft YaHei", sans-serif; }
      body { display: grid; min-height: 100vh; margin: 0; place-items: center; background: #f4f7fb; color: #172033; }
      main { width: min(420px, calc(100% - 48px)); padding: 40px; text-align: center; background: #fff; border: 1px solid #e7ebf1; border-radius: 20px; box-shadow: 0 18px 48px rgba(23, 32, 51, .10); }
      a { display: inline-block; margin-top: 14px; padding: 12px 22px; color: #fff; text-decoration: none; background: #2563eb; border-radius: 10px; }
    </style>
    <script>location.replace('/zysd/');</script>
  </head>
  <body>
    <main>
      <h1>江苏电力曲线计算器</h1>
      <p>正在进入页面……</p>
      <a href="/zysd/">立即打开</a>
    </main>
  </body>
</html>
`,
    'utf8',
  );
}
fs.writeFileSync(path.join(outputDirectory, '.nojekyll'), '', 'utf8');
