import assert from 'node:assert/strict';
import { mkdir, mkdtemp, readFile, readdir, rename, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { createController } from '../controller.mjs';

test('records intent, clicks, observation and human readback in order', async () => {
  const root = await mkdtemp(join(tmpdir(), 'chess-harness-'));
  try {
    const points = [];
    const dir = join(root, 'game');
    const app = {
      getScreenshot: async () => Buffer.from('synthetic screenshot'),
      click: async point => points.push(point),
    };
    const controller = await createController(app, dir);
    await assert.rejects(controller.click('e2e4', [10, 20]), /Capture/);
    const pre = await controller.observe();
    const post = await controller.click('e2e4', [10, 20], [10, 40]);
    assert.deepEqual(points, [[10, 20], [10, 40]]);
    await assert.rejects(controller.click('second', [10, 20]), /Verify/);
    await assert.rejects(controller.verify('accepted', pre, 'old frame'), /latest/);
    await controller.verify('accepted', post, 'Pawn seen on e4');
    const entries = (await readFile(join(dir, 'actions.jsonl'), 'utf8')).trim().split('\n')
      .map(line => JSON.parse(line));
    assert.deepEqual(entries.map(entry => entry.phase), ['intent', 'clicked', 'observed', 'verified']);
    assert(entries.every(entry => entry.id === entries[0].id));
    assert.deepEqual(entries[0].pre, pre.ref);
    assert.deepEqual(entries.at(-1).evidence, post.ref);
  } finally {
    await rm(root, { force: true, recursive: true });
  }
});

test('uncertain clicks require fresh observation and a readback before recovery', async () => {
  const root = await mkdtemp(join(tmpdir(), 'chess-harness-'));
  try {
    const app = {
      getScreenshot: async () => [{ bytes: Buffer.from('synthetic screenshot') }],
      click: async () => { throw new Error('interrupted'); },
    };
    const controller = await createController(app, join(root, 'game'));
    const pre = await controller.observe();
    await assert.rejects(controller.click('e2e4', [10, 20]), /interrupted/);
    await assert.rejects(controller.verify('uncertain', pre, 'old frame'), /latest/);
    await assert.rejects(controller.click('e2e4', [10, 20]), /Verify/);
    await controller.verify('uncertain', await controller.observe(), 'Screen inspected after interruption');
  } finally {
    await rm(root, { force: true, recursive: true });
  }
});

test('a controller cannot use its old frame after the run directory is renamed and reused', async () => {
  const root = await mkdtemp(join(tmpdir(), 'chess-harness-'));
  try {
    const dir = join(root, 'game');
    const moved = join(root, 'refused');
    const points = [];
    let screenshots = 0;
    const app = {
      getScreenshot: async () => Buffer.from(`synthetic screenshot ${++screenshots}`),
      click: async point => points.push(point),
    };
    const stale = await createController(app, dir);
    const oldFrame = await stale.observe();
    await rename(dir, moved);
    const fresh = await createController(app, dir);
    const freshFrame = await fresh.observe();

    await assert.rejects(stale.click('stale move', [10, 20]), /run directory was removed or replaced/);
    await assert.rejects(stale.observe(), /run directory was removed or replaced/);
    assert.deepEqual(points, []);
    assert.equal(screenshots, 2);
    assert.deepEqual(await readdir(dir), [freshFrame.ref.file]);
    assert.deepEqual(await readdir(moved), [oldFrame.ref.file]);

    const post = await fresh.click('fresh move', [30, 40]);
    await fresh.verify('accepted', post, 'Fresh controller used its own frame');
    assert.deepEqual(points, [[30, 40]]);
  } finally {
    await rm(root, { force: true, recursive: true });
  }
});

test('replacement during the first click stops the second click and ledger writes', async () => {
  const root = await mkdtemp(join(tmpdir(), 'chess-harness-'));
  try {
    const dir = join(root, 'game');
    const moved = join(root, 'moved');
    const points = [];
    const controller = await createController({
      getScreenshot: async () => Buffer.from('synthetic screenshot'),
      click: async point => {
        points.push(point);
        if (points.length === 1) {
          await rename(dir, moved);
          await mkdir(dir);
        }
      },
    }, dir);
    await controller.observe();

    await assert.rejects(controller.click('two clicks', [10, 20], [30, 40]),
      /run directory was removed or replaced/);
    assert.deepEqual(points, [[10, 20]]);
    assert.deepEqual(await readdir(dir), []);
    const intent = JSON.parse(await readFile(join(moved, 'actions.jsonl'), 'utf8'));
    assert.equal(intent.phase, 'intent');
  } finally {
    await rm(root, { force: true, recursive: true });
  }
});
