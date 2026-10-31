// Real-browser artifact tests, using the checksum-pinned Archify browser harness.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [skill, artifact, modelPath] = process.argv.slice(2);
const { ChromeVisualBrowser, findChrome } = await import(pathToFileURL(path.join(skill, 'bin/visual-check.mjs')));
const { createViewerClick } = await import(pathToFileURL(path.join(skill, '../test/helpers/viewer-click.mjs')));
const chrome = findChrome();
assert.ok(chrome, 'Real Chrome is required for diagram interaction checks');
const model = JSON.parse(fs.readFileSync(modelPath, 'utf8'));
const browser = new ChromeVisualBrowser(chrome);
try {
  const session = await browser.sessionPromise;
  const send = (method, params = {}) => browser.cdp.send(method, params, session);
  async function run(expression) {
    const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    assert.equal(result.exceptionDetails, undefined, result.exceptionDetails?.exception?.description);
    return result.result?.value;
  }
  await send('Emulation.setFocusEmulationEnabled', { enabled: true });
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
  await send('Page.addScriptToEvaluateOnNewDocument', { source: `
    window.smokeErrors=[];
    addEventListener('error',e=>smokeErrors.push(e.message));
    addEventListener('unhandledrejection',e=>smokeErrors.push(String(e.reason)));
  ` });
  const click = await createViewerClick({ send, run, timeout: 10000 });
  const loaded = browser.cdp.waitFor('Page.loadEventFired', session);
  await send('Page.navigate', { url: pathToFileURL(artifact).href });
  await loaded;
  await run('document.fonts.ready');
  await run('Archify.viewerChromeLayout.whenStable()');
  assert.equal(await run('document.documentElement.dataset.theme'), 'light');
  assert.equal(await run('document.querySelector(".diagram-container > svg").dataset.awsStyle'), 'reference');
  const key = async (key, code, windowsVirtualKeyCode) => {
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode });
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode });
  };
  await click('#btn-theme');
  assert.equal(await run('document.documentElement.dataset.theme'), 'dark');
  assert.equal(await run('getComputedStyle(document.querySelector(".diagram-container > svg")).backgroundColor'), 'rgb(255, 255, 255)');
  assert.deepEqual(await run(`Array.from(document.querySelectorAll('rect.atlas-node'), n => getComputedStyle(n).fill)`),
    model.components.map(() => 'rgb(255, 255, 255)'));
  assert.equal(await run('getComputedStyle(document.getElementById("btn-node-finder")).color'), 'rgb(84, 91, 100)');
  const first = model.components[0];
  await click('#btn-node-finder');
  assert.equal(await run('Archify.finder.isOpen()'), true);
  await send('Input.insertText', { text: first.id });
  const found = await run(`[...document.querySelectorAll('#node-finder-results .node-finder-result')].map(n=>n.dataset.nodeId)`);
  assert.ok(found.includes(first.id), 'Finder must return the authored stable node ID');
  await click(`#node-finder-results [data-node-id="${first.id}"]`);
  assert.equal(await run('Archify.focus.active()'), first.id);
  assert.ok(await run(`Archify.sourceEvidence.node(${JSON.stringify(first.id)}).length`));
  await key('Escape', 'Escape', 27);
  const edge = model.connections[0];
  await click('#btn-route-probe');
  assert.equal(await run('Archify.routeProbe.active()'), 'source');
  await click(`.diagram-container > svg [data-node-id="${edge.from}"]`);
  assert.equal(await run('Archify.routeProbe.active()'), 'target');
  await click(`.diagram-container > svg [data-node-id="${edge.to}"]`);
  assert.deepEqual(await run('Archify.routeProbe.result().nodes'), [edge.from, edge.to]);
  await key('Escape', 'Escape', 27);
  assert.deepEqual(await run('smokeErrors'), []);
  assert.deepEqual(await run(`performance.getEntriesByType('resource').map(e=>e.name).filter(n=>/^https?:/.test(n))`), []);
  const awsImages = await run('document.querySelectorAll(".diagram-container > svg image[data-aws-icon]").length');
  assert.equal(awsImages, model.components.filter(n => n.tag?.startsWith('AWS')).length);
  const iconLayout = await run(`Array.from(document.querySelectorAll('image[data-aws-icon]'), image => ({
    width: Number(image.getAttribute('width')), height: Number(image.getAttribute('height')),
    labelY: Number(image.parentElement.querySelector('text[data-node-label]').getAttribute('y')),
    bottom: Number(image.getAttribute('y')) + Number(image.getAttribute('height')),
    aspect: image.getAttribute('preserveAspectRatio'),
    filter: getComputedStyle(image.parentElement.querySelector('rect.atlas-node')).filter
  }))`);
  for (const icon of iconLayout) {
    assert.equal(icon.width, 64); assert.equal(icon.height, 64);
    assert.ok(icon.labelY > icon.bottom, 'AWS label must sit below the primary icon');
    assert.equal(icon.aspect, 'xMidYMid meet'); assert.equal(icon.filter, 'none');
  }
  console.log(JSON.stringify({ status: 'pass', theme: 'native-click', finder: 'native-text-input',
    focus: first.id, source_evidence: 'present', route: [edge.from, edge.to],
    route_input: 'native-clicks', aws_images: awsImages, presentation: 'aws-reference',
    aws_icon_size: 64, external_resources: 0, runtime_errors: 0 }));
} finally {
  await browser.close();
}
