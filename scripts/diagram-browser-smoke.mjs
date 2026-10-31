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
  async function navigate(theme) {
    const url = pathToFileURL(artifact);
    if (theme) url.searchParams.set('theme', theme);
    const loaded = browser.cdp.waitFor('Page.loadEventFired', session);
    await send('Page.navigate', { url: url.href });
    await loaded;
    await run('document.fonts.ready');
    await run('Archify.viewerChromeLayout.whenStable()');
  }
  // Resolve actual rendered colors, including alpha panels, for both native themes.
  function readPalette() {
    const svg = document.querySelector('.diagram-container > svg');
    const canvas = document.createElement('canvas').getContext('2d');
    canvas.canvas.width = canvas.canvas.height = 1;
    const rgba = color => {
      canvas.clearRect(0, 0, 1, 1);
      canvas.fillStyle = color;
      canvas.fillRect(0, 0, 1, 1);
      const [r, g, b, a] = canvas.getImageData(0, 0, 1, 1).data;
      return [r, g, b, a / 255];
    };
    const over = (front, back) => front.slice(0, 3).map((c, i) =>
      c * front[3] + back[i] * (1 - front[3])).concat(1);
    const background = element => {
      const ancestors = [];
      for (let el = element; el; el = el.parentElement) ancestors.unshift(el);
      return ancestors.reduce((color, el) =>
        over(rgba(getComputedStyle(el).backgroundColor), color), [255, 255, 255, 1]);
    };
    const luminance = color => color.slice(0, 3).map(c => {
      c /= 255;
      return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    }).reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);
    const contrast = (foreground, backdrop) => {
      const a = luminance(over(rgba(foreground), backdrop));
      const b = luminance(backdrop);
      return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    };
    const root = getComputedStyle(document.documentElement);
    const mask = rgba(getComputedStyle(svg).getPropertyValue('--mask').trim());
    const nodeBackground = over(mask, background(svg));
    const labels = [...svg.querySelectorAll('g[data-node-id] > text')];
    const edges = [...svg.querySelectorAll('[data-edge-from] text')];
    const controls = ['btn-theme', 'btn-node-finder', 'btn-route-probe'].map(id => document.getElementById(id));
    return {
      theme: document.documentElement.dataset.theme,
      canvas: rgba(getComputedStyle(svg).backgroundColor),
      container: rgba(getComputedStyle(svg.parentElement).backgroundColor),
      background: rgba(root.getPropertyValue('--bg').trim()),
      mask,
      nodes: [...svg.querySelectorAll('rect.atlas-node')].map(n => rgba(getComputedStyle(n).fill)),
      counts: { labels: labels.length, edges: edges.length, controls: controls.length },
      contrast: {
        labels: Math.min(...labels.map(n => contrast(getComputedStyle(n).fill, nodeBackground))),
        edges: Math.min(...edges.map(n => contrast(getComputedStyle(n).fill, nodeBackground))),
        controls: Math.min(...controls.map(n => contrast(getComputedStyle(n).color, background(n)))),
      },
      stored: localStorage.getItem('archify-theme'),
      query: new URL(location.href).searchParams.get('theme'),
    };
  }
  async function palette(theme, query, stored) {
    await run(`Promise.all(document.getAnimations().filter(a =>
      a.effect?.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})))`);
    const current = await run(`(${readPalette.toString()})()`);
    assert.deepEqual(await run('smokeErrors'), [], `${theme}: runtime errors`);
    assert.equal(current.theme, theme);
    assert.equal(current.query, query, 'Theme clicks must preserve the URL query');
    if (stored) assert.equal(current.stored, stored, 'Native theme selection must persist');
    assert.deepEqual(current.canvas, current.background, `${theme}: SVG background must follow --bg`);
    assert.deepEqual(current.container, current.background, `${theme}: canvas container must follow --bg`);
    assert.deepEqual(current.mask, current.background, `${theme}: diagram masks must share the selected background`);
    assert.deepEqual(current.nodes, model.components.map(() => current.mask), `${theme}: node fills must follow --mask`);
    for (const kind of ['labels', 'edges', 'controls']) {
      assert.ok(current.counts[kind] > 0, `Expected visible ${kind}`);
      assert.ok(current.contrast[kind] >= 4.5,
        `${theme}: ${kind} contrast ${current.contrast[kind].toFixed(2)} is below 4.5`);
    }
    return current;
  }
  await navigate('light');
  assert.equal(await run('document.querySelector(".diagram-container > svg").dataset.awsStyle'), 'reference');
  const light = await palette('light', 'light');
  const key = async (key, code, windowsVirtualKeyCode) => {
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode });
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode });
  };
  await click('#btn-theme');
  const dark = await palette('dark', 'light', 'dark');
  assert.notDeepEqual(dark.canvas, light.canvas, 'Light and Dark must use different canvas colors');
  assert.notDeepEqual(dark.mask, light.mask, 'Light and Dark must use different node fills');
  await navigate();
  await palette('dark', null, 'dark');
  await click('#btn-theme');
  const returned = await palette('light', null, 'light');
  assert.deepEqual(returned.canvas, light.canvas);
  assert.deepEqual(returned.mask, light.mask);
  await navigate();
  await palette('light', null, 'light');
  await navigate('dark');
  await palette('dark', 'dark', 'light'); // Explicit query wins over the saved preference.
  await navigate('light');
  await palette('light', 'light', 'light');
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
  console.log(JSON.stringify({ status: 'pass', theme: 'native-light-dark-light', theme_persistence: 'bare-url-reload',
    theme_query: 'explicit-overrides-saved', theme_contrast: { light: light.contrast, dark: dark.contrast }, finder: 'native-text-input',
    focus: first.id, source_evidence: 'present', route: [edge.from, edge.to],
    route_input: 'native-clicks', aws_images: awsImages, presentation: 'aws-reference',
    aws_icon_size: 64, external_resources: 0, runtime_errors: 0 }));
} finally {
  await browser.close();
}
