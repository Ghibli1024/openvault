#!/usr/bin/env node
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { BrowserBridge } from '/Users/Totoro/.npm-global/lib/node_modules/@jackwener/opencli/dist/browser/index.js';

const MIXIN_KEY_ENC_TAB = [
  46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
  33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
  61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
  36, 20, 34, 44, 52,
];

function parseArgs(argv) {
  const args = {
    workspace: 'bilibili-favorites-sync',
  };
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (!item.startsWith('--')) {
      continue;
    }
    const key = item.slice(2);
    const next = argv[index + 1];
    if (next && !next.startsWith('--')) {
      args[key] = next;
      index += 1;
    } else {
      args[key] = true;
    }
  }
  return args;
}

function mixinKey(imgKey, subKey) {
  const raw = `${imgKey}${subKey}`;
  return MIXIN_KEY_ENC_TAB.map((index) => raw[index] || '').join('').slice(0, 32);
}

function signWbi(params, imgKey, subKey) {
  const withTimestamp = { ...params, wts: String(Math.floor(Date.now() / 1000)) };
  const sorted = {};
  for (const key of Object.keys(withTimestamp).sort()) {
    sorted[key] = String(withTimestamp[key]).replace(/[!'()*]/g, '');
  }
  const query = new URLSearchParams(sorted).toString().replace(/\+/g, '%20');
  sorted.w_rid = crypto.createHash('md5').update(query + mixinKey(imgKey, subKey)).digest('hex');
  return sorted;
}

async function fetchJson(url, headers) {
  const response = await fetch(url, { headers });
  if (!response.ok) {
    throw new Error(`request failed: ${response.status} ${response.statusText} ${url}`);
  }
  return await response.json();
}

function cookieHeader(cookies) {
  return cookies.map((cookie) => `${cookie.name}=${cookie.value}`).join('; ');
}

function folderSummary(folder) {
  return {
    id: String(folder.id ?? folder.fid ?? ''),
    title: String(folder.title ?? ''),
    media_count: Number(folder.media_count ?? 0),
  };
}

async function fetchAllFolderItems(folder, headers, imgKey, subKey, limitItemsPerFolder) {
  const items = [];
  const pageSize = 40;
  let pageNumber = 1;
  while (true) {
    const signed = new URLSearchParams(
      signWbi({ media_id: folder.id, pn: pageNumber, ps: pageSize }, imgKey, subKey),
    ).toString().replace(/\+/g, '%20');
    const payload = await fetchJson(`https://api.bilibili.com/x/v3/fav/resource/list?${signed}`, headers);
    const data = payload?.data ?? {};
    const medias = Array.isArray(data.medias) ? data.medias : [];
    for (const media of medias) {
      items.push({
        folder_id: String(folder.id),
        folder_name: folder.title,
        media,
      });
      if (limitItemsPerFolder && items.length >= limitItemsPerFolder) {
        return items;
      }
    }
    if (!medias.length || medias.length < pageSize) {
      break;
    }
    if (limitItemsPerFolder && items.length >= limitItemsPerFolder) {
      break;
    }
    pageNumber += 1;
  }
  return items;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const outputJson = args['output-json'] ? path.resolve(String(args['output-json'])) : '';
  const limitFolders = args['limit-folders'] ? Number(args['limit-folders']) : 0;
  const limitItemsPerFolder = args['limit-items-per-folder'] ? Number(args['limit-items-per-folder']) : 0;

  let lastError = null;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    const bridge = new BrowserBridge();
    let page = null;
    try {
      page = await bridge.connect({ timeout: 30, workspace: String(args.workspace) });
      await page.goto('https://www.bilibili.com', { settleMs: 1200 });
      const cookies = await page.getCookies({ domain: 'bilibili.com' });
      if (!cookies.length) {
        throw new Error('no Bilibili cookies found in the connected Chrome profile');
      }

      const headers = {
        cookie: cookieHeader(cookies),
        referer: 'https://www.bilibili.com/',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        accept: 'application/json, text/plain, */*',
      };

      const nav = await fetchJson('https://api.bilibili.com/x/web-interface/nav', headers);
      if (nav?.code !== 0 || !nav?.data?.mid) {
        throw new Error(`failed to resolve current user: ${JSON.stringify(nav).slice(0, 500)}`);
      }

      const uid = String(nav.data.mid);
      const imgKey = String(nav.data?.wbi_img?.img_url || '').split('/').pop()?.split('.')[0] || '';
      const subKey = String(nav.data?.wbi_img?.sub_url || '').split('/').pop()?.split('.')[0] || '';
      if (!imgKey || !subKey) {
        throw new Error('missing WBI signing keys in nav response');
      }

      const folderQuery = new URLSearchParams(signWbi({ up_mid: uid }, imgKey, subKey))
        .toString()
        .replace(/\+/g, '%20');
      const foldersPayload = await fetchJson(
        `https://api.bilibili.com/x/v3/fav/folder/created/list-all?${folderQuery}`,
        headers,
      );
      const folders = Array.isArray(foldersPayload?.data?.list)
        ? foldersPayload.data.list.map(folderSummary)
        : [];

      const limitedFolders = limitFolders > 0 ? folders.slice(0, limitFolders) : folders;
      const items = [];
      for (const folder of limitedFolders) {
        const folderItems = await fetchAllFolderItems(folder, headers, imgKey, subKey, limitItemsPerFolder);
        items.push(...folderItems);
      }

      const payload = {
        uid,
        fetched_at: new Date().toISOString(),
        source: 'browser-bridge-cookie-fetch',
        folders: limitedFolders,
        items,
      };

      if (outputJson) {
        await fs.mkdir(path.dirname(outputJson), { recursive: true });
        await fs.writeFile(outputJson, JSON.stringify(payload, null, 2), 'utf8');
        process.stdout.write(`${outputJson}\n`);
        return;
      }

      process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
      return;
    } catch (error) {
      lastError = error;
      const message = error instanceof Error ? error.message : String(error);
      if (attempt >= 2 || !message.includes('Extension not connected')) {
        throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, 1200));
    } finally {
      try {
        await page?.closeWindow();
      } catch {}
      await bridge.close().catch(() => {});
    }
  }

  throw lastError instanceof Error ? lastError : new Error(String(lastError));
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.stack || error.message : String(error)}\n`);
  process.exit(1);
});
